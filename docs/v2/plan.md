# Plan Module Spec

## Overview

The plan module (`plan/`) handles loading, validating, and hashing plan files. It takes raw JSON files and produces validated `Plan` objects for the engine.

This is a Core (L2) module. It depends only on the Contracts layer.

## Dependencies (Contracts only)

| Contract Domain | Types Used |
|----------------|-----------|
| **plan** | `Plan`, `PlanItem`, `Epic`, `Story`, `Task` |
| **exceptions** | `PlanLoadError`, `PlanValidationError` |

No dependency on provider, renderer, item, sync, or config domains.

## Classes

### PlanLoader

Loads plan entities from JSON files and constructs a `Plan` object.

```python
class PlanLoader:
    def load(self, epics_path: Path, stories_path: Path, tasks_path: Path) -> Plan:
        """Load and parse plan JSON files into a validated Plan model.

        Args:
            epics_path: Path to epics JSON file.
            stories_path: Path to stories JSON file.
            tasks_path: Path to tasks JSON file.

        Returns:
            A validated Plan instance.

        Raises:
            PlanLoadError: If any file is missing, unreadable, contains
                invalid JSON, or data doesn't match the schema.
        """
```

**Behavior:**
1. Verify all files exist
2. Read and parse JSON
3. Construct `Plan` via Pydantic (schema validation happens here)
4. Return validated `Plan`

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
| No duplicate IDs | Epic, story, and task IDs must be unique within their type |
| At least one epic | Plan must contain at least one epic |
| Task -> story ref | Every `task.parent_id` must reference an existing story |
| Story -> epic ref | Every `story.parent_id` must reference an existing epic |
| Sub-item consistency | `parent.sub_item_ids` must match children whose `parent_id` points back |
| Dependency refs | Every entry in `depends_on` must reference an existing item |
| No orphan stories | Every story must have at least one task |

**Note on v2 model changes:** With `PlanItem` base class using `parent_id` and `sub_item_ids` instead of `epic_id`/`story_id`/`story_ids`/`task_ids`, the validator uses the unified fields:
- `task.parent_id` replaces `task.story_id`
- `story.parent_id` replaces `story.epic_id`
- `epic.sub_item_ids` replaces `epic.story_ids`
- `story.sub_item_ids` replaces `story.task_ids`

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
1. Serialize each entity list via Pydantic `model_dump(mode="json", by_alias=True)`
2. JSON-encode with `sort_keys=True, separators=(",", ":")`  (canonical form)
3. SHA-256 hash, truncate to first 12 hex characters

**Idempotency guarantee:** Two plans with identical content produce the same `plan_id`, regardless of file paths or load order. This is how the engine detects already-synced plans via body markers.

## Contracts Validation

The plan module confirms these plan domain types are sufficient:

| Type | Fields Used by Plan Module |
|------|--------------------------|
| `Plan` | `.epics: list[Epic]`, `.stories: list[Story]`, `.tasks: list[Task]` |
| `PlanItem` | `.id`, `.parent_id`, `.sub_item_ids`, `.depends_on` |
| `Epic` | (inherits PlanItem, no additional fields needed by this module) |
| `Story` | (inherits PlanItem, no additional fields needed by this module) |
| `Task` | (inherits PlanItem, no additional fields needed by this module) |

All fields used here are defined in the `PlanItem` base class. The plan module does not need to distinguish between Epic/Story/Task for validation — it works through `PlanItem` properties. Entity type is determined by position in `Plan.epics`/`.stories`/`.tasks`.

## Changes from v1

| v1 | v2 | Rationale |
|----|-----|-----------|
| Free functions: `load_plan()`, `validate_plan()`, `compute_plan_id()` | Classes: `PlanLoader`, `PlanValidator`, `PlanHasher` | OOP design, testable, mockable |
| Validator checks `task.story_id`, `story.epic_id`, `epic.story_ids`, `story.task_ids` | Validator checks `parent_id` and `sub_item_ids` uniformly | PlanItem base class unifies the hierarchy |
| Functions imported directly by engine | SDK calls plan module, passes `Plan` to engine | Engine doesn't do I/O |
