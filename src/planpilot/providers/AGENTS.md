# PROVIDERS KNOWLEDGE BASE

## OVERVIEW
Provider integration layer: provider factory selection, dry-run provider behavior, and concrete provider package boundaries.

## STRUCTURE
```text
src/planpilot/providers/
|- factory.py            # `create_provider()` mapping and instantiation policy
|- dry_run.py            # Offline `DryRunProvider` + operation log model
|- base.py               # ProviderContext base marker
|- github/               # GitHub concrete implementation + generated client
`- __init__.py           # Public exports for provider layer
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Add provider type mapping | `src/planpilot/providers/factory.py` | Update `PROVIDERS` and constructor wiring |
| Validate offline apply path | `src/planpilot/providers/dry_run.py` | Deterministic placeholders + operation tracing |
| Understand provider state base | `src/planpilot/providers/base.py` | `ProviderContext` marker for resolved state |
| GitHub provider internals | `src/planpilot/providers/github/provider.py` | Context resolution and provider CRUD |

## CONVENTIONS
- Keep `factory.py` as the single provider-name to implementation map.
- `DryRunProvider` must remain network-free and deterministic for tests/E2E.
- Concrete provider internals stay under their provider package (for example `github/`).
- Provider layer API exposed through `__init__.py` should stay minimal and stable.

## ANTI-PATTERNS
- Do not wire provider-specific logic into engine or SDK modules.
- Do not add non-deterministic behavior in `DryRunProvider` IDs/operation logs.
- Do not bypass factory mapping by constructing concrete providers in unrelated modules.
- Do not hand-edit generated GitHub GraphQL client as primary change workflow.
