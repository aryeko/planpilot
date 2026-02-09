# PROJECT KNOWLEDGE BASE

**Generated:** 2026-02-09 20:23 (Asia/Jerusalem)
**Commit:** 8d229f5
**Branch:** v2

## OVERVIEW
`planpilot` is a Python 3.11+ CLI/SDK that syncs structured plan JSON (epics/stories/tasks) into GitHub Issues + Projects v2.
Core stack: Pydantic contracts, async orchestration engine, generated GraphQL client (ariadne-codegen), pytest/ruff/mypy.

## STRUCTURE
```text
planpilot/
|- src/planpilot/              # Runtime package (SDK + engine + providers)
|  |- cli.py                   # CLI parser + command execution
|  |- sdk.py                   # Composition root and sync-map persistence
|  |- engine/engine.py         # Discovery -> upsert -> enrich -> relations
|  |- providers/github/        # GitHub adapter + generated GraphQL client
|  |- contracts/               # Provider-agnostic types and ABCs
|  `- plan/                    # Plan loading, validation, hashing
|- tests/                      # Mirrors runtime domains; includes offline E2E
|- docs/                       # Architecture, module specs, decisions
`- .github/workflows/          # CI, release, TestPyPI/PyPI pipeline
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| CLI flow and exits | `src/planpilot/cli.py` | `build_parser()`, `main()`, summary text |
| Runtime composition | `src/planpilot/sdk.py` | `PlanPilot.from_config()` + `sync()` orchestration entry |
| Sync pipeline | `src/planpilot/engine/engine.py` | 5-phase flow and relation wiring |
| Provider contract boundary | `src/planpilot/contracts/provider.py` | Provider ABC expected by engine |
| GitHub behavior | `src/planpilot/providers/github/provider.py` | Context resolution + CRUD + relations |
| Plan semantics | `src/planpilot/plan/validator.py` | Strict/partial validation behavior |
| Renderer output markers | `src/planpilot/renderers/markdown.py` | Metadata block drives idempotent discovery |
| Release behavior | `.github/workflows/release.yml`, `RELEASE.md` | Semantic release -> TestPyPI smoke -> PyPI |

## CODE MAP
| Symbol | Type | Location | Refs | Role |
|--------|------|----------|------|------|
| `PlanPilot` | class | `src/planpilot/sdk.py` | high | SDK facade and sync-map persistence |
| `SyncEngine` | class | `src/planpilot/engine/engine.py` | high | Core pipeline coordinator |
| `Provider` | ABC | `src/planpilot/contracts/provider.py` | medium | Adapter contract used by engine |
| `GitHubProvider` | class | `src/planpilot/providers/github/provider.py` | high | Concrete GitHub implementation |
| `build_parser` | function | `src/planpilot/cli.py` | medium | CLI argument schema |

## CONVENTIONS
- Source/tests mirror by domain (`src/planpilot/<module>` <-> `tests/<module>`).
- Engine is orchestration-only; provider/network details stay behind `Provider`.
- Runtime typing is strict (`disallow_untyped_defs = true`); generated client is excluded from strict checks.
- CLI mode is explicit (`--dry-run` xor `--apply`) and dry-run persists to `<sync_path>.dry-run`.
- Tooling is Ruff + mypy + pytest via Poe tasks (`poe check` as local gate).

## ANTI-PATTERNS (THIS PROJECT)
- Do not add live network/API calls in tests; keep tests mock/fake/offline.
- Do not hand-edit release versions/tags; semantic-release owns bump/changelog/tag.
- Do not make sync destructive (no auto-delete semantics in current scope).
- Do not hand-edit generated GraphQL client files as primary source of truth.

## UNIQUE STYLES
- Idempotency relies on deterministic `plan_id` + issue-body metadata markers.
- Discovery is provider-search-first using metadata marker query.
- Project workflow fields (status/priority/iteration) remain provider-authoritative post-create.

## COMMANDS
```bash
poetry install
poe lint
poe format
poe test
poe test-e2e
poe typecheck
poe check
poetry run planpilot --help
```

## NOTES
- CI runs lint/typecheck and tests across Python 3.11/3.12/3.13.
- Release pipeline publishes to TestPyPI first; smoke failure blocks PyPI publish.
- Ignore `__pycache__/` noise when mapping structure/hotspots.
