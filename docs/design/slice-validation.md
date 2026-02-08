# Slice Input Validation (Design Spec)

## Problem Statement

`slice_epics_for_sync()` operates on raw Python dicts loaded from JSON without
any structural validation. It trusts that:

- Each loaded file is a JSON **array** (not null, not an object).
- Every epic dict has an `"id"` key.
- Every story dict has `"id"` and `"epic_id"` keys.
- Every task dict has `"id"` and `"story_id"` keys.

If any of these assumptions are violated, the function produces silently wrong
output (empty slices, missing files) or raises an unhelpful `TypeError` /
`KeyError` from deep inside the iteration logic.

The `slice_cli()` wrapper now catches `KeyError` and `JSONDecodeError`, but the
error messages don't tell the user *which* field is missing or *which* file was
malformed.

## Current Code

```python
def slice_epics_for_sync(epics_path, stories_path, tasks_path, out_dir):
    epics = _read_json(epics_path)      # Could be None, dict, int, ...
    stories = _read_json(stories_path)
    tasks = _read_json(tasks_path)

    stories_by_id = {s["id"]: s for s in stories}  # KeyError if missing "id"

    for epic in epics:
        eid = epic["id"]                             # KeyError if missing
        story_ids = epic.get("story_ids", [])
        ...
```

## Proposed Solution

### 1. Add `_validate_list()` helper

```python
def _validate_list(data: Any, label: str, required_keys: list[str]) -> list[dict[str, Any]]:
    """Validate that data is a list of dicts with required keys.

    Args:
        data: Parsed JSON value.
        label: Human-readable name for error messages (e.g. "epics").
        required_keys: Keys that every dict in the list must have.

    Returns:
        The validated list (unchanged).

    Raises:
        ValueError: If data is not a list of dicts or missing required keys.
    """
    if not isinstance(data, list):
        raise ValueError(f"{label}: expected a JSON array, got {type(data).__name__}")

    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"{label}[{i}]: expected an object, got {type(item).__name__}")
        for key in required_keys:
            if key not in item:
                raise ValueError(f"{label}[{i}]: missing required key '{key}'")

    return data
```

### 2. Call validation after loading

```python
def slice_epics_for_sync(epics_path, stories_path, tasks_path, out_dir):
    epics = _validate_list(_read_json(epics_path), "epics", ["id"])
    stories = _validate_list(_read_json(stories_path), "stories", ["id", "epic_id"])
    tasks = _validate_list(_read_json(tasks_path), "tasks", ["id", "story_id"])
    ...
```

### 3. Update `slice_cli` error handling

The existing `except (json.JSONDecodeError, KeyError, ValueError)` block already
catches `ValueError`, so no CLI changes are needed. The user will now see:

```
Error: Invalid input format: stories[2]: missing required key 'epic_id'
```

instead of:

```
Error: Invalid input format: 'epic_id'
```

### 4. Add tests

| Test | Input | Expected |
|------|-------|----------|
| `test_slice_rejects_non_array_epics` | `epics.json` = `{}` | `ValueError: epics: expected a JSON array` |
| `test_slice_rejects_missing_id_in_story` | story without `"id"` | `ValueError: stories[0]: missing required key 'id'` |
| `test_slice_rejects_missing_story_id_in_task` | task without `"story_id"` | `ValueError: tasks[0]: missing required key 'story_id'` |
| `test_slice_rejects_null_json` | `epics.json` = `null` | `ValueError: epics: expected a JSON array` |

## Implementation Scope

- Modified file: `src/planpilot/slice.py` (add `_validate_list`, ~20 lines;
  update 3 call sites).
- New tests: `tests/test_slice.py` (4 new test functions, ~60 lines).
- No other files affected.

## Backward Compatibility

Fully backward compatible for valid inputs. Invalid inputs that previously
produced silent corruption or opaque `KeyError` will now produce clear
`ValueError` messages caught by the existing `slice_cli` error handler.

## Success Criteria

- All existing slice tests pass unchanged.
- New validation tests cover array type check and required-key checks.
- Manual test: running `planpilot-slice` with a malformed file prints a
  human-readable error message.
