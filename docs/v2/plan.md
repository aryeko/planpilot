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
                - Single-file (unified): one file with all items, each
                  having an explicit `type` field

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

### PlanValidator

Validates relational integrity across plan entities.

```python
class PlanValidator:
    def validate(self, plan: Plan) -> None:
        """Validate relational integrity of a plan.

        Raises:
            PlanValidationError: Aggregated list of all validation errors found.
        """
```

**Validation rules:**

| Rule | Description |
|------|------------|
| No duplicate IDs | All item IDs must be globally unique |
| At least one epic | Plan must contain at least one item of type EPIC |
| Valid type | Every item must have a valid `PlanItemType` |
| Parent ref | Every item's `parent_id` must reference an existing item of the correct parent type (task→story, story→epic) |
| Sub-item consistency | `parent.sub_item_ids` must match children whose `parent_id` points back |
| Hierarchy depth | Tasks must have a story parent; stories must have an epic parent; epics have no parent |
| Dependency refs | Every entry in `depends_on` must reference an existing item |
| No childless stories | Every story must have at least one task |
| Type-specific required fields | See per-type matrix below |

**Per-type required fields:**

`id`, `type`, and `title` are required on `PlanItem` at the model level (Pydantic). The validator enforces additional per-type requirements:

| Field | Epic | Story | Task |
|-------|------|-------|------|
| `goal` | Required | Required | Optional |
| `parent_id` | None (must be absent) | Required (epic) | Required (story) |
| `sub_item_ids` | Required (stories) | Required (tasks) | None |
| `spec_ref` | Optional | Optional | Optional |
| `requirements` | Optional | Optional | Required |
| `acceptance_criteria` | Optional | Required | Optional |
| `verification` | None | None | Required |
| `estimate` | None | Optional | Required |
| `depends_on` | Optional | Optional | Optional |

**Error aggregation:** All errors are collected and raised together in a single `PlanValidationError`, so users see every issue in one pass.

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
1. Serialize `plan.items` via Pydantic `model_dump(mode="json", by_alias=True)`
2. JSON-encode with `sort_keys=True, separators=(",", ":")`  (canonical form)
3. SHA-256 hash, truncate to first 12 hex characters

**Idempotency guarantee:** Two plans with identical content produce the same `plan_id`, regardless of file paths or load order. This is how the engine detects already-synced plans via body markers.

## Contracts Validation

The plan module confirms these plan domain types are sufficient:

| Type | Fields Used by Plan Module |
|------|--------------------------|
| `Plan` | `.items: list[PlanItem]` |
| `PlanItem` | `.id`, `.type`, `.parent_id`, `.sub_item_ids`, `.depends_on`, `.verification` |
| `PlanItemType` | `EPIC`, `STORY`, `TASK` — used for hierarchy and type-specific validation |

All fields live on the flat `PlanItem` class. Entity type is determined by `item.type`. The validator uses the type to enforce hierarchy rules (e.g. tasks must parent to stories).

## Changes from v1

| v1 | v2 | Rationale |
|----|-----|-----------|
| Free functions: `load_plan()`, `validate_plan()`, `compute_plan_id()` | Classes: `PlanLoader`, `PlanValidator`, `PlanHasher` | OOP design, testable, mockable |
| Separate `Epic`, `Story`, `Task` subclasses | Single flat `PlanItem` with `type: PlanItemType` | Simpler model, no inheritance, type-driven validation |
| Validator checks `task.story_id`, `story.epic_id`, `epic.story_ids`, `story.task_ids` | Validator checks `parent_id` and `sub_item_ids` uniformly using `type` for hierarchy rules | Unified hierarchy fields |
| Functions imported directly by engine | SDK calls plan module, passes `Plan` to engine | Engine doesn't do I/O |
