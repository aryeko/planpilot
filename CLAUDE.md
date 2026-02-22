# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All tasks use [poethepoet](https://github.com/nat-n/poethepoet). Run with `poe <task>` or `poetry run poe <task>`:

```bash
poe check          # lint + format-check + typecheck + non-E2E tests (run before pushing)
poe lint           # ruff check
poe format         # ruff format (auto-fix)
poe typecheck      # mypy src/planpilot
poe test           # pytest -v --ignore=tests/e2e (includes coverage report)
poe test-e2e       # offline E2E suite (tests/e2e/test_cli_e2e.py)
poe docs-links     # validate internal markdown links
poe workflow-lint  # actionlint on .github/workflows/
```

Run a single test file:
```bash
poetry run pytest tests/engine/test_engine.py -v
```

Run a single test by name:
```bash
poetry run pytest tests/engine/test_engine.py -v -k "test_discovery"
```

Regenerate the GitHub GraphQL client (requires `gh` auth):
```bash
poe gen-gql
```

## Architecture

planpilot is a CLI/SDK that syncs structured plan files (epics/stories/tasks) to GitHub Issues + Projects v2. It follows a strict layered architecture with downward-only dependencies:

```
Contracts → Core → SDK → CLI
```

**Contracts** (`src/planpilot/core/contracts/`) — Pure Pydantic models and ABCs. Six domains: `plan`, `item`, `sync`, `config`, `provider`, `renderer`. The `Provider` and `BodyRenderer` ABCs live here (not in Core) because they define what the system needs, not how it works.

**Core** (`src/planpilot/core/`) — Runtime business logic. Key modules:
- `engine/engine.py` — `SyncEngine`: 5-phase async pipeline (Discovery → Upsert → Enrich → Relations → Result). Epics/stories/tasks are processed sequentially by type level; operations within a level run concurrently via `asyncio.TaskGroup` gated by `asyncio.Semaphore(config.max_concurrent)`.
- `plan/` — JSON plan loading, relational validation (`PlanValidator`), deterministic hashing (`PlanHasher`).
- `providers/github/` — GitHub REST+GraphQL adapter. The GraphQL client under `providers/github/github_gql/` is **generated** by `ariadne-codegen` — do not hand-edit it.
- `providers/dry_run.py` — In-memory `DryRunProvider` used in `--dry-run` mode; no external API calls.
- `renderers/markdown.py` — `MarkdownRenderer`: renders issue bodies with a `PLANPILOT_META_V1` block at the top for idempotent discovery.

**SDK** (`src/planpilot/sdk.py`) — The sole composition root. `PlanPilot.from_config()` wires all Core domains together. This is the only place that sees all Core modules simultaneously. Re-exports selected Contracts types for external callers.

**CLI** (`src/planpilot/cli/`) — Thin I/O wrapper. Imports only from the SDK public API and `cli/persistence/`. Never imports Core directly.

## Key Conventions

- **Layer discipline**: CLI → SDK only. SDK → Core. Core → Contracts. Never bypass layers.
- **Typing**: `disallow_untyped_defs = true` enforced by mypy on all runtime code in `src/planpilot`. Tests are not mypy-gated.
- **Tests are offline**: Use mocks/fakes (`tests/fakes/`) instead of live GitHub API calls. E2E tests call `planpilot.cli.main()` directly — no shell subprocess.
- **Test layout mirrors source**: `tests/engine/` → `src/planpilot/core/engine/`, etc.
- **Coverage target**: 90%+ branch coverage.
- **Commit format**: Conventional Commits required (`feat`, `fix`, `docs`, `chore`, etc.), max 72-char header. Enforced by CI (commitlint) and local hook (`./scripts/install-hooks.sh`).
- **Generated code**: `src/planpilot/core/providers/github/github_gql/` is excluded from mypy and coverage. Regenerate with `poe gen-gql`.
- **Worktrees**: Create under `.worktrees/` in the project root. Run `poetry install` after creating.

## Anti-Patterns

- Do not import GitHub-specific modules into `engine/` or `contracts/`.
- Do not add direct provider/network calls in tests.
- Do not bypass `PlanValidator` before sync execution.
- Do not write side effects in dry-run code paths.
- Do not re-introduce legacy root domain modules outside `core/` and `cli/`.
- Do not hand-edit the generated GraphQL client as the primary change workflow.

## Documentation Update Policy

For any user-visible behavior or architecture change, update docs in the same PR. Quick mapping:

| Change | Docs to update |
|--------|---------------|
| CLI flags/commands | `README.md`, `docs/modules/cli.md`, `docs/how-it-works.md` |
| Engine/sync semantics | `docs/design/engine.md`, `docs/how-it-works.md`, `docs/modules/sdk.md` |
| Provider behavior | `docs/modules/providers.md`, `docs/modules/github-provider.md` |
| Config/schema | `README.md`, `docs/modules/config.md`, `docs/reference/plan-schemas.md` |
| Plugin/skills | `src/planpilot/skills/*/SKILL.md`, `src/planpilot/commands/*.md`, `src/planpilot/.claude-plugin/plugin.json`, `docs/guides/plugin-skills-guide.md`, `docs/reference/plugin-reference.md` |
| CI/release | `RELEASE.md`, `docs/reference/workflows-reference.md` |

Run `poe docs-links` after updating docs to verify no broken internal links.
