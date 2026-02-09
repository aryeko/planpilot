# Multi-Epic Sync Support (Design Spec)

## Problem Statement

planpilot currently enforces a **single-epic constraint** at two levels:

1. **Validator** (`plan/validator.py` line 22): `if len(plan.epics) != 1` raises
   a `PlanValidationError`.
2. **Engine** (`sync/engine.py` line 89): Calls `validate_plan(plan)` before
   any work.

This means multi-epic plans must be sliced externally before syncing. There are
currently **two separate implementations** of this slicing logic:

| Location | Runs via | Validation | Filename safety | Part of package |
|----------|----------|------------|-----------------|-----------------|
| `src/planpilot/slice.py` | `planpilot-slice` CLI | None | No (uses raw `epic["id"]` in filenames) | Yes |
| `skills/.../slice_epics_for_sync.py` | Standalone script | Yes (checks required keys, object type) | Yes (`safe_epic_id_for_filename()` with SHA1 fallback) | No |

The problems:

1. **Feature split**: The better implementation (validation, safe filenames) is a
   standalone script in `skills/`, not installable via pip. The package version
   in `src/planpilot/slice.py` has weaker validation and no filename safety.
2. **External orchestration required**: Users must manually run `planpilot-slice`,
   then loop over slices calling `planpilot` per epic. The SKILL.md documents a
   12-line bash template for this.
3. **No merged sync map**: Each epic produces its own sync map. There is no
   built-in merge step.
4. **Cross-epic dependencies are silently dropped**: When slicing, `depends_on`
   entries pointing to tasks in other epics are filtered out. The user gets no
   warning about this.

## Proposed Solution

### Phase 1: Consolidate slice logic into the package

Merge the best features of both implementations into `src/planpilot/slice.py`:

```python
# From skills/ helper — add to slice.py:
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")

def _safe_epic_id(value: str) -> str:
    """Return a filesystem-safe fragment for an epic ID."""
    cleaned = _SAFE_FILENAME_RE.sub("_", value).strip("._-")
    if cleaned:
        return cleaned
    return f"epic_{hashlib.sha1(value.encode()).hexdigest()[:12]}"
```

Add structural validation before slicing (from `slice-validation.md` spec):

```python
def slice_epics_for_sync(...) -> list[SliceResult]:
    epics = _validate_list(_read_json(epics_path), "epics", ["id", "story_ids"])
    stories = _validate_list(_read_json(stories_path), "stories", ["id", "epic_id"])
    tasks = _validate_list(_read_json(tasks_path), "tasks", ["id", "story_id"])
    ...
```

Return a structured result instead of `None`:

```python
@dataclass
class SliceResult:
    """Result of slicing a single epic."""
    epic_id: str
    epics_path: Path
    stories_path: Path
    tasks_path: Path
    dropped_deps: list[tuple[str, str]]  # [(task_id, dropped_dep_id), ...]
```

Warn about dropped cross-epic dependencies:

```python
for task in epic_tasks:
    original_deps = task.get("depends_on", [])
    kept = [d for d in original_deps if d in epic_task_ids]
    dropped = [d for d in original_deps if d not in epic_task_ids]
    if dropped:
        logger.warning(
            "Task %s: dropped %d cross-epic dep(s): %s",
            task["id"], len(dropped), dropped,
        )
    task["depends_on"] = kept
```

### Phase 2: Add dedicated multi-epic orchestration command (historical proposal)

This section reflects an early proposal. Current canonical CLI behavior is single-track: use `planpilot` directly for multi-epic plans.

```shell
planpilot \
  --repo owner/repo \
  --project-url https://github.com/orgs/org/projects/1 \
  --epics-path .plans/epics.json \
  --stories-path .plans/stories.json \
  --tasks-path .plans/tasks.json \
  --sync-path .plans/github-sync-map.json \
  --dry-run
```

Internal flow:

```text
1. Load plan files
2. If len(epics) == 1:
     Sync directly (current behavior, no slicing needed)
3. If len(epics) > 1:
     a. Slice into per-epic files in a temp directory
     b. For each slice:
        - Validate (single-epic validator)
        - Compute plan_id
        - Run sync (dry-run or apply)
        - Collect per-epic SyncResult
     c. Merge per-epic sync maps into a combined sync map
     d. Write combined sync map to --sync-path
     e. Write per-epic sync maps to --sync-path.<epic_id>.json
4. Print combined summary
```

### Phase 3: Lift the single-epic constraint (optional, longer-term)

Refactor the engine to handle multiple epics natively:

- Update `validate_plan()` to accept `N >= 1` epics.
- Update `_upsert_*` methods to handle multiple epics in one pass.
- Update `_set_relations` to handle cross-epic relations.

This eliminates the need for slicing entirely but is a larger change. The
Phase 2 orchestrator provides the same UX with lower risk.

### Merged Sync Map

The combined sync map includes all epics, stories, and tasks across slices:

```json
{
  "plan_id": "combined-<hash>",
  "repo": "owner/repo",
  "project_url": "https://github.com/orgs/org/projects/1",
  "epics": {
    "E-1": {"issue_number": 1, "url": "...", "node_id": "..."},
    "E-2": {"issue_number": 2, "url": "...", "node_id": "..."}
  },
  "stories": { ... },
  "tasks": { ... }
}
```

## Implementation Scope

### Phase 1 (consolidate slice)

| File | Change |
|------|--------|
| `src/planpilot/slice.py` | Add `_safe_epic_id()`, `_validate_list()`, `SliceResult` dataclass, cross-epic dep warnings, return `list[SliceResult]` |
| `tests/test_slice.py` | Add tests for safe filenames, validation errors, cross-epic dep warnings |
| `skills/.../slice_epics_for_sync.py` | Deprecate; update SKILL.md to reference `planpilot-slice` |

### Phase 2 (sync-all command)

| File | Change |
|------|--------|
| `src/planpilot/cli.py` | (Historical) Considered adding a dedicated `sync-all` subcommand |
| `src/planpilot/sync/orchestrator.py` | New module: `MultiEpicOrchestrator` that slices, syncs per-epic, merges results |
| `src/planpilot/models/sync.py` | Add `merge_sync_maps()` utility |
| `tests/sync/test_orchestrator.py` | New test module |

### Phase 3 (native multi-epic, optional)

| File | Change |
|------|--------|
| `src/planpilot/plan/validator.py` | Remove `len(plan.epics) != 1` check, add multi-epic cross-reference validation |
| `src/planpilot/sync/engine.py` | Support N epics in upsert/enrich/relations phases |

## Backward Compatibility

- **Phase 1**: Fully backward compatible. `planpilot-slice` gains features,
  existing behavior preserved.
- **Phase 2**: New command only. Existing `planpilot` command unchanged.
- **Phase 3**: `validate_plan()` relaxation is backward compatible (accepts
  a superset of inputs).

## Migration Path

1. Ship Phase 1. Update SKILL.md to use `planpilot-slice` exclusively.
2. Ship Phase 2. Update SKILL.md to use canonical `planpilot` invocation for multi-epic plans.
3. (Optional) Ship Phase 3. Simplify SKILL.md to a single `planpilot` call.

## Success Criteria

- `planpilot-slice` produces safe filenames for any epic ID (unicode, special
  chars, empty string).
- `planpilot-slice` warns about dropped cross-epic dependencies.
- `planpilot` syncs a 3-epic plan end-to-end with one command.
- Combined sync map merges all per-epic entries correctly.
- `skills/.../slice_epics_for_sync.py` is removed or marked deprecated.
