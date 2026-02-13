# PROJECT KNOWLEDGE BASE

**Generated:** 2026-02-13 (Asia/Jerusalem)

## OVERVIEW

`planpilot` is a Python 3.11+ CLI/SDK that syncs structured plans (epics/stories/tasks) into GitHub Issues + Projects v2.

Core stack:

- Pydantic models and contracts
- Async orchestration engine
- Generated GraphQL client (ariadne-codegen)
- Ruff, mypy, pytest, poe tasks

## STRUCTURE

```text
planpilot/
|- src/planpilot/
|  |- sdk.py                        # SDK facade and composition root
|  |- cli/                          # CLI package (parser, app, commands, progress, persistence)
|  `- core/                         # Runtime domains (auth/config/contracts/engine/plan/providers/renderers/targets)
|- tests/                           # Domain-mirrored tests + CLI/sdk coverage + E2E
|- docs/                            # Architecture, module specs, decisions, plans
|- skills/                          # Optional Claude/OpenCode skills
`- .github/workflows/               # CI + release pipeline
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| CLI entrypoints | `src/planpilot/cli/parser.py`, `src/planpilot/cli/app.py` | parser + main routing |
| Config scaffolding | `src/planpilot/core/config/scaffold.py` | detect target, detect plans, scaffold config |
| Config loading | `src/planpilot/core/config/loader.py` | JSON load + path resolution + provider-specific checks |
| Runtime composition | `src/planpilot/sdk.py` | `PlanPilot.from_config()` and sync lifecycle |
| Sync pipeline | `src/planpilot/core/engine/engine.py` | discovery -> upsert -> enrich -> relations |
| Contracts boundary | `src/planpilot/core/contracts/` | provider-agnostic types and ABCs |
| Provider implementation | `src/planpilot/core/providers/github/provider.py` | GitHub adapter behavior |
| Provider extension points | `src/planpilot/core/providers/factory.py`, `src/planpilot/core/providers/dry_run.py` | provider mapping and dry-run path |
| Plan semantics | `src/planpilot/core/plan/validator.py` | strict/partial semantics |
| Renderer markers | `src/planpilot/core/renderers/markdown.py` | metadata block for idempotent discovery |

## CONVENTIONS

- CLI imports from `planpilot` public API and approved CLI helpers, not core internals.
- SDK is the only composition root that sees all core domains.
- Core domains are cohesive and live under `src/planpilot/core/*`.
- Keep runtime typing strict (`disallow_untyped_defs = true`) and treat generated GraphQL code as generated artifacts.

## ANTI-PATTERNS

- Do not add direct provider/network calls in tests.
- Do not bypass semantic-release and CI-based release gates.
- Do not hand-edit generated GraphQL client output as the primary change workflow.
- Do not re-introduce legacy root domain modules (`src/planpilot/{auth,config,providers,...}`) outside `core/` and `cli/`.
