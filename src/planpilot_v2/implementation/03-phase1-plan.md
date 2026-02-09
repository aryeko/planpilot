# Phase 1: Plan Module

**Layer:** L2 (Core)
**Branch:** `v2/plan`
**Phase:** 1 (parallel with auth, renderers, engine)
**Dependencies:** Contracts only (`planpilot_v2.contracts.plan`, `planpilot_v2.contracts.config`, `planpilot_v2.contracts.exceptions`)
**Design doc:** [`../docs/modules/plan.md`](../docs/modules/plan.md)

---

## Files to Create

| File | Contents |
|------|----------|
| `plan/__init__.py` | Exports `PlanLoader`, `PlanValidator`, `PlanHasher` |
| `plan/loader.py` | `PlanLoader` |
| `plan/validator.py` | `PlanValidator` |
| `plan/hasher.py` | `PlanHasher` |

---

## PlanLoader

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
1. Determine mode from `PlanPaths` (unified vs separate)
2. Verify all referenced files exist
3. Read and parse JSON
4. For multi-file: tag each item with `PlanItemType` based on which file it came from
5. Construct `Plan(items=[...])` via Pydantic
6. Return validated `Plan`

**Unified mode input:** `{ "items": [ { "id": "E1", "type": "EPIC", ... } ] }`
**Multi-file mode input:** `[ { "id": "E1", ... } ]` (array, type assigned from file role)

---

## PlanValidator

```python
class PlanValidator:
    def validate(self, plan: Plan, *, mode: str = "strict") -> None:
        """Validate relational integrity. Raises PlanValidationError with all errors."""
```

### Validation Rules (both modes)

| Rule | Description |
|------|-------------|
| No duplicate IDs | All item IDs must be globally unique |
| Valid type | Every item must have a valid `PlanItemType` |
| Parent hierarchy | If parent is loaded: task->story, story->epic. Epics cannot have a parent |
| Sub-item consistency | If both sides loaded, `sub_item_ids` must match inverse of `parent_id` |
| Per-type required fields | See matrix below |

### Per-Type Required Fields (validator enforces)

| Field | Epic | Story | Task |
|-------|------|-------|------|
| `goal` | Required | Required | Required |
| `parent_id` | Forbidden | Optional (must ref Epic) | Optional (must ref Story) |
| `requirements` | Required | Required | Required |
| `acceptance_criteria` | Required | Required | Required |

### Reference Checks by Mode

| Rule | `strict` | `partial` |
|------|----------|-----------|
| `parent_id` exists | Required | Optional when parent not loaded |
| `depends_on` exists | Required | Optional when dep not loaded |
| Invalid loaded ref type | Error | Error |

---

## PlanHasher

```python
class PlanHasher:
    def compute_plan_id(self, plan: Plan) -> str:
        """Compute a deterministic 12-char hex plan ID."""
```

**Algorithm:**
1. Sort `plan.items` by `(item.type.value, item.id)`
2. Serialize each via `model_dump(mode="json", by_alias=True, exclude_none=True)`
3. Normalize optional containers (missing and empty canonicalized to same)
4. JSON-encode with `sort_keys=True, separators=(",", ":")`
5. SHA-256 hash, truncate to first 12 hex characters

---

## Test Strategy

| Test File | Key Cases |
|-----------|-----------|
| `test_loader.py` | Load unified JSON, load multi-file, missing file -> PlanLoadError, invalid JSON -> PlanLoadError, empty plan |
| `test_validator.py` | Duplicate IDs, invalid parent type (task->task), strict mode missing ref, partial mode missing ref OK, epic with parent_id, missing goal/requirements/acceptance_criteria, sub_item consistency |
| `test_hasher.py` | Same plan -> same hash, reordered items -> same hash, different plan -> different hash, empty vs missing containers -> same hash, hash is 12 hex chars |
