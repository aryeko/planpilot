# RUNTIME KNOWLEDGE BASE

## OVERVIEW
Runtime package for SDK composition, sync orchestration, contracts, plan loading/validation, and provider/rendering adapters.

## STRUCTURE
```text
src/planpilot/
|- cli.py                    # CLI entry and output formatting
|- sdk.py                    # Public facade and runtime composition
|- engine/                   # 5-phase orchestration pipeline
|- contracts/                # Provider-agnostic models + ABCs + errors
|- providers/                # Provider factory and implementations
|- plan/                     # Plan loader/validator/hasher
|- renderers/                # Body rendering implementations
`- auth/                     # Token resolver strategy + factory
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Compose runtime from config | `src/planpilot/sdk.py` | `load_config()`, `PlanPilot.from_config()`, `sync()` |
| CLI behavior and exits | `src/planpilot/cli.py` | `build_parser()`, `_format_summary()`, `main()` |
| Sync ordering/concurrency | `src/planpilot/engine/engine.py` | discovery -> upsert -> enrich -> relations |
| Provider contract | `src/planpilot/contracts/provider.py` | Single boundary engine depends on |
| Domain schemas | `src/planpilot/contracts/plan.py`, `src/planpilot/contracts/sync.py` | Typed plan/sync payloads |
| Plan semantics | `src/planpilot/plan/validator.py` | strict vs partial behaviors |
| Renderer metadata | `src/planpilot/renderers/markdown.py` | idempotency markers in issue body |

## CONVENTIONS
- Keep engine orchestration-only; no provider-specific API calls outside `providers/`.
- Keep SDK as composition root; avoid wiring providers/renderers directly in unrelated modules.
- Preserve strict typing (`disallow_untyped_defs = true`) for runtime code.
- Keep provider-facing data in contracts; provider internals stay provider-local.

## ANTI-PATTERNS
- Do not import GitHub-specific modules into `engine/` or `contracts/`.
- Do not bypass `PlanValidator` before sync execution.
- Do not write side effects in dry-run code paths.
- Do not duplicate orchestration logic outside `SyncEngine`.
