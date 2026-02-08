# PROJECT KNOWLEDGE BASE

**Generated:** 2026-02-08 20:07 (Asia/Jerusalem)
**Commit:** 60d7dfd
**Branch:** main

## OVERVIEW
`planpilot` is a Python 3.11+ CLI that syncs plan JSON (epics/stories/tasks) into GitHub Issues + Projects v2.
Core stack: Pydantic models, async `gh` CLI integration, provider abstraction, pytest/ruff/mypy toolchain.

## STRUCTURE
```text
planpilot/
├── src/planpilot/            # Runtime package
│   ├── cli.py                # Main CLI + argument wiring
│   ├── sync/engine.py        # 5-phase orchestration core
│   ├── providers/github/     # gh GraphQL implementation
│   ├── models/               # Pydantic domain types
│   └── plan/                 # load/validate/hash plan inputs
├── tests/                    # Mirrors src/planpilot layout
├── docs/                     # How-it-works, schemas, architecture
└── .github/workflows/        # CI, release, test-release pipelines
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| CLI behavior/flags | `src/planpilot/cli.py` | `main()` builds `SyncConfig`, selects dry-run/apply path |
| Sync orchestration | `src/planpilot/sync/engine.py` | Setup -> discovery -> upsert -> enrich -> relations |
| Provider contracts | `src/planpilot/providers/base.py` | All new providers must satisfy this ABC |
| GitHub API behavior | `src/planpilot/providers/github/provider.py` | GraphQL/gh calls, project field resolution |
| Plan schema/validation | `src/planpilot/models/plan.py`, `src/planpilot/plan/validator.py` | Type + relational checks |
| Rendering issue bodies | `src/planpilot/rendering/markdown.py` | Uses shared blocks from `components.py` |
| Release logic | `.github/workflows/release.yml`, `RELEASE.md` | Semantic release + TestPyPI smoke gate |

## CODE MAP
| Symbol | Type | Location | Refs | Role |
|--------|------|----------|------|------|
| `SyncEngine` | class | `src/planpilot/sync/engine.py` | 4 | Core pipeline coordinator |
| `Provider` | ABC | `src/planpilot/providers/base.py` | 6 | Adapter contract boundary |
| `GitHubProvider` | class | `src/planpilot/providers/github/provider.py` | 2 | Concrete GitHub implementation |
| `build_parser` | function | `src/planpilot/cli.py` | 1 | CLI argument schema |
| `load_plan` | function | `src/planpilot/plan/loader.py` | 1 | JSON -> `Plan` loader |

## CONVENTIONS
- Source and tests are mirrored by domain (`src/planpilot/<module>` <-> `tests/<module>`).
- Runtime code is fully typed (`mypy` with `disallow_untyped_defs = true`).
- Lint/format are Ruff-only; line length is 120.
- CLI mode is explicit and mutually exclusive: exactly one of `--dry-run` or `--apply`.
- Provider boundary is strict: sync engine depends on `Provider` + `BodyRenderer`, not on GitHub details.

## ANTI-PATTERNS (THIS PROJECT)
- Do not add real network/API calls in tests; test suite uses mocks/fakes.
- Do not bypass release automation by manual version/tag edits; semantic-release owns bump/tag/changelog.
- Do not break Conventional Commit format; CI + commit hook enforce it.
- Do not make sync destructive (no auto-delete semantics in v1 scope).

## UNIQUE STYLES
- Plan identity uses deterministic hash (`plan_id`) and issue body markers for idempotent upserts.
- Dry-run mode is offline preview (enumerate outputs without mutating GitHub).
- GitHub provider uses `gh` CLI + GraphQL constants in `queries.py`.

## COMMANDS
```bash
poetry install
poe lint
poe format
poe test
poe typecheck
poe check
poetry run planpilot --help
```

## NOTES
- Python support matrix in CI: 3.11, 3.12, 3.13.
- Release workflow publishes to TestPyPI first; smoke failure blocks PyPI publish.
- `__pycache__/` directories exist in repo tree; ignore them when mapping architecture.
