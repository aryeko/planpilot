# SDK Reference

## Primary entrypoints

| API | Description |
|---|---|
| `load_config(path)` | Load and validate `PlanPilotConfig` from JSON |
| `load_plan(...)` | Convenience loader for explicit plan paths |
| `PlanPilot.from_config(config, renderer_name="markdown", progress=None)` | Build SDK facade from validated config |

## `PlanPilot` methods

| Method | Returns | Side effects |
|---|---|---|
| `sync(plan=None, dry_run=False)` | `SyncResult` | Provider mutations only in apply mode |
| `discover_remote_plan_ids()` | `list[str]` | No provider mutations |
| `map_sync(plan_id, dry_run=False)` | `MapSyncResult` | No provider mutations; returns result only |
| `clean(dry_run=False, all_plans=False)` | `CleanResult` | Provider deletions only in apply mode |

## Result objects

| Type | Key fields |
|---|---|
| `SyncResult` | `sync_map`, `items_created`, `dry_run` |
| `MapSyncResult` | `sync_map`, `added`, `updated`, `removed`, `remote_plan_items`, `dry_run` |
| `CleanResult` | `plan_id`, `items_deleted`, `dry_run` |

## Ownership rules

- SDK workflows return typed result objects.
- Local file persistence is caller-owned.
- CLI persistence behavior lives in `planpilot.cli.persistence.*`.

## Exceptions surface

| Exception | Typical source |
|---|---|
| `ConfigError` | Config load/validation |
| `PlanLoadError` | Plan file read/parse |
| `PlanValidationError` | Plan semantic validation |
| `AuthenticationError` | Token resolution/provider auth |
| `ProviderError` | Provider operation failures |
| `SyncError` | Sync/cleanup execution failures |

## Minimal usage

```python
from planpilot import PlanPilot, load_config

config = load_config("planpilot.json")
pp = await PlanPilot.from_config(config)
result = await pp.sync(dry_run=True)
print(result.sync_map.plan_id)
```
