# Plan Module Spec

## Overview

The plan module (`plan/`) handles loading, validating, and hashing plan files. It takes raw JSON files and produces validated `Plan` objects for the engine.

This is a Core (L2) module. It depends only on the Contracts layer.

## Dependencies (Contracts only)

| Contract Domain | Types Used |
|----------------|-----------|
| **plan** | `Plan`, `PlanItem`, `PlanItemType` |
| **config** | `PlanPaths` |
| **exceptions** | `PlanLoadError`, `PlanValidationError` |

No dependency on provider, renderer, item, or sync domains.

## Classes

### PlanLoader

Loads plan entities from JSON files and constructs a `Plan` object. Supports both multi-file input (separate epics/stories/tasks files) and single-file input (all items in one file with `type` field).

```python
class PlanLoader:
    def load(self, plan_paths: PlanPaths) -> Plan:
        """Load and parse plan JSON files into a validated Plan model.

        Args:
            plan_paths: PlanPaths configuration from the config domain.
                Supports two modes:
                - Multi-file: separate epics/stories/tasks paths set
                - Single-file (unified): one file with an `items` array,
                  each item having an explicit `type` field

        Returns:
            A validated Plan instance with flat items list.

        Raises:
            PlanLoadError: If any file is missing, unreadable, contains
                invalid JSON, or data doesn't match the schema.
        """
```

**Behavior:**
1. Determine mode from `PlanPaths` (unified path vs separate epics/stories/tasks paths)
2. Verify all referenced files exist
3. Read and parse JSON
4. For multi-file input: tag each item with the appropriate `PlanItemType` based on which file it came from
5. Construct `Plan(items=[...])` via Pydantic (schema validation happens here)
6. Return validated `Plan`

**Error handling:** All file I/O and JSON parse errors are wrapped in `PlanLoadError` with descriptive messages. Pydantic `ValidationError` is also wrapped.

**Unified file shape (canonical):**

```json
{
  "items": [
    {
      "id": "E1",
      "type": "EPIC",
      "title": "Epic title",
      "goal": "Outcome",
      "requirements": ["R1"],
      "acceptance_criteria": ["A1"]
    }
  ]
}
```

**Multi-file shapes (canonical):**

`epics.json`:

```json
[
  {
    "id": "E1",
    "title": "Epic title",
    "goal": "Outcome",
    "requirements": ["R1"],
    "acceptance_criteria": ["A1"]
  }
]
```

`stories.json`:

```json
[
  {
    "id": "S1",
    "title": "Story title",
    "parent_id": "E1",
    "goal": "Outcome",
    "requirements": ["R1"],
    "acceptance_criteria": ["A1"]
  }
]
```

`tasks.json`:

```json
[
  {
    "id": "T1",
    "title": "Task title",
    "parent_id": "S1",
    "goal": "Outcome",
    "requirements": ["R1"],
    "acceptance_criteria": ["A1"]
  }
]
```

For multi-file mode, root shape is a JSON array in each file. `type` is optional input and ignored if provided; the loader assigns type from file role.

### PlanValidator

Validates relational integrity across plan entities.

```python
class PlanValidator:
    def validate(self, plan: Plan, *, mode: str = "strict") -> None:
        """Validate relational integrity of a plan.

        Args:
            mode: "strict" or "partial".

        Raises:
            PlanValidationError: Aggregated list of all validation errors found.
        """
```

**Validation modes:**

| Mode | Behavior |
|------|----------|
| `strict` | All parent/dependency references must resolve to loaded items |
| `partial` | Missing references are allowed when the referenced item is not loaded in this run |

**Validation rules (both modes):**

| Rule | Description |
|------|------------|
| No duplicate IDs | All item IDs must be globally unique |
| Valid type | Every item must have a valid `PlanItemType` |
| Parent hierarchy type rules | If parent is loaded, transitions must be task->story and story->epic. Epics cannot have a parent in v2 |
| Sub-item consistency | `sub_item_ids` is optional/derived. If both sides are loaded, it must match the inverse of `parent_id` references |
| Type-specific required fields | See per-type matrix below |

**Reference checks by mode:**

| Rule | `strict` | `partial` |
|------|----------|-----------|
| `parent_id` reference exists | Required | Optional when parent is missing from loaded input |
| `depends_on` reference exists | Required | Optional when dependency is missing from loaded input |
| Invalid loaded reference type (e.g. task parented by task) | Error | Error |

**Per-type required fields:**

`id`, `type`, and `title` are required on `PlanItem` at the model level (Pydantic). The validator enforces additional per-type requirements:

| Field | Epic | Story | Task |
|-------|------|-------|------|
| `goal` | Required | Required | Required |
| `parent_id` | Forbidden | Optional (must reference Epic when loaded) | Optional (must reference Story when loaded) |
| `sub_item_ids` | Optional | Optional | Optional |
| `spec_ref` | Optional | Optional | Optional |
| `requirements` | Required | Required | Required |
| `acceptance_criteria` | Required | Required | Required |
| `verification` | Optional | Optional | Optional |
| `estimate` | Optional | Optional | Optional |
| `depends_on` | Optional | Optional | Optional |

**Error aggregation:** All errors are collected and raised together in a single `PlanValidationError`, so users see every issue in one pass.

**Rationale for strict required fields:** v2 intentionally enforces `goal`, `requirements`, and `acceptance_criteria` for epics, stories, and tasks to keep plan quality consistent and make rendered issue bodies actionable by default.

### PlanHasher

Computes a deterministic plan identifier for idempotent syncs.

```python
class PlanHasher:
    def compute_plan_id(self, plan: Plan) -> str:
        """Compute a deterministic 12-char hex plan ID.

        The ID is derived from a SHA-256 hash of the canonically-serialized
        plan. Same plan content always produces the same ID.

        Returns:
            12-character hex string.
        """
```

**Algorithm:**
1. Canonicalize item order: sort `plan.items` by `(item.type.value, item.id)`
2. Serialize each item via `model_dump(mode="json", by_alias=True, exclude_none=True)`
3. Normalize optional containers so semantically equivalent representations hash equally:
   - Missing and empty optional lists/maps are canonicalized to the same representation
   - Empty optional containers are dropped from canonical JSON
4. JSON-encode with `sort_keys=True, separators=(",", ":")` (canonical form)
5. SHA-256 hash, truncate to first 12 hex characters

**Idempotency guarantee:** Two plans with identical semantics produce the same `plan_id`, regardless of file paths, load order, or empty-vs-missing optional container representation.

## Contracts Validation

The plan module confirms these plan domain types are sufficient:

| Type | Fields Used by Plan Module |
|------|--------------------------|
| `Plan` | `.items: list[PlanItem]` |
| `PlanItem` | `.id`, `.type`, `.parent_id`, `.sub_item_ids`, `.depends_on`, `.goal`, `.requirements`, `.acceptance_criteria`, `.verification` |
| `PlanItemType` | `EPIC`, `STORY`, `TASK` — used for hierarchy and type-specific validation |

All fields live on the flat `PlanItem` class. Entity type is determined by `item.type`. The validator treats `parent_id` as canonical hierarchy data and validates optional `sub_item_ids` as a consistency projection.

## Changes from v1

| v1 | v2 | Rationale |
|----|-----|-----------|
| Free functions: `load_plan()`, `validate_plan()`, `compute_plan_id()` | Classes: `PlanLoader`, `PlanValidator`, `PlanHasher` | OOP design, testable, mockable |
| Separate `Epic`, `Story`, `Task` subclasses | Single flat `PlanItem` with `type: PlanItemType` | Simpler model, no inheritance, type-driven validation |
| Validator checks `task.story_id`, `story.epic_id`, `epic.story_ids`, `story.task_ids` | Validator checks `parent_id` and `sub_item_ids` uniformly using `type` for hierarchy rules | Unified hierarchy fields |
| Schema uses typed linkage fields (`story_id`, `epic_id`, `story_ids`, `task_ids`) | Schema uses `parent_id` + optional `sub_item_ids` | One hierarchy model across all item types |
| Strict-only reference validation | Configurable `strict`/`partial` validation mode | Supports partial plan sync workflows |
| Functions imported directly by engine | SDK calls plan module, passes `Plan` to engine | Engine doesn't do I/O |
