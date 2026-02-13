# Plan Module Spec

The plan module (`core/plan/`) handles loading, validating, and hashing plan files. It takes raw JSON files and produces validated `Plan` objects for the engine.

This is a Core module. It depends only on the Contracts layer (see [contracts.md](../design/contracts.md) for type definitions).

## PlanLoader

Loads plan entities from JSON files and constructs a `Plan` object. Supports both multi-file input (separate epics/stories/tasks files) and single-file input (all items in one file with `type` field).

```python
class PlanLoader:
    def load(self, plan_paths: PlanPaths) -> Plan:
        """Load and parse plan JSON files into a validated Plan model.

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

**Error handling:** All file I/O, JSON parse, and Pydantic `ValidationError` are wrapped in `PlanLoadError`.

### Plan File Shapes

**Unified mode:**

```json
{
  "items": [
    { "id": "E1", "type": "EPIC", "title": "Epic title", "goal": "Outcome",
      "requirements": ["R1"], "acceptance_criteria": ["A1"] }
  ]
}
```

**Multi-file mode** (root shape is a JSON array; `type` is optional/ignored — loader assigns type from file role):

```json
[
  { "id": "E1", "title": "Epic title", "goal": "Outcome",
    "requirements": ["R1"], "acceptance_criteria": ["A1"] }
]
```

## PlanValidator

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

### Validation Modes

| Mode | Behavior |
|------|----------|
| `strict` | All parent/dependency references must resolve to loaded items |
| `partial` | Missing references are allowed when the referenced item is not loaded in this run |

### Validation Rules (both modes)

| Rule | Description |
|------|------------|
| No duplicate IDs | All item IDs must be globally unique |
| Valid type | Every item must have a valid `PlanItemType` |
| Parent hierarchy type rules | If parent is loaded: task->story, story->epic. Epics cannot have a parent |
| Sub-item consistency | If both sides are loaded, `sub_item_ids` must match inverse of `parent_id` references |
| Type-specific required fields | See matrix below |

### Reference Checks by Mode

| Rule | `strict` | `partial` |
|------|----------|-----------|
| `parent_id` reference exists | Required | Optional when parent is missing from loaded input |
| `depends_on` reference exists | Required | Optional when dependency is missing from loaded input |
| Invalid loaded reference type (e.g. task parented by task) | Error | Error |

### Per-Type Required Fields

`id`, `type`, and `title` are required at the model level (Pydantic). The validator enforces:

| Field | Epic | Story | Task |
|-------|------|-------|------|
| `goal` | Required | Required | Required |
| `parent_id` | Forbidden | Optional (must ref Epic) | Optional (must ref Story) |
| `requirements` | Required | Required | Required |
| `acceptance_criteria` | Required | Required | Required |
| All other fields | Optional | Optional | Optional |

**Error aggregation:** All errors are collected and raised together in a single `PlanValidationError`.

## PlanHasher

Computes a deterministic plan identifier for idempotent syncs.

```python
class PlanHasher:
    def compute_plan_id(self, plan: Plan) -> str:
        """Compute a deterministic 12-char hex plan ID."""
```

**Algorithm:**
1. Sort `plan.items` by `(item.type.value, item.id)`
2. Serialize each item via `model_dump(mode="json", by_alias=True, exclude_none=True)`
3. Normalize optional containers (missing and empty canonicalized to same representation)
4. JSON-encode with `sort_keys=True, separators=(",", ":")`
5. SHA-256 hash, truncate to first 12 hex characters

**Idempotency guarantee:** Two plans with identical semantics produce the same `plan_id`, regardless of file paths, load order, or empty-vs-missing optional container representation.
