# AGENTS.md - planpilot

The contract for working in this repo. Self-contained: act on it with only this
repo checked out. Read the source file or doc that owns your task before
changing code.

`planpilot` is a Python 3.11+ CLI/SDK that syncs structured plans
(epics, stories, tasks) to GitHub Issues and Projects v2.

## Ground Truth

| Task | Read |
| --- | --- |
| CLI behavior | `src/planpilot/cli/`, `docs/modules/cli.md` |
| Runtime composition | `src/planpilot/sdk.py`, `docs/modules/sdk.md` |
| Sync semantics | `src/planpilot/core/engine/engine.py`, `docs/how-it-works.md` |
| Plan schema and validation | `src/planpilot/core/plan/`, `docs/reference/plan-schemas.md` |
| GitHub provider | `src/planpilot/core/providers/github/`, `docs/modules/github-provider.md` |
| Tests and E2E | `tests/`, `docs/testing/e2e.md` |
| Release and CI | `.github/workflows/`, `RELEASE.md` |

## Boundaries

- CLI imports from the SDK public API and approved CLI helpers, not core internals.
- `src/planpilot/sdk.py` is the only composition root.
- Core domains stay provider-agnostic except under `src/planpilot/core/providers/`.
- Provider-facing contracts live in `src/planpilot/core/contracts/`.
- Do not hand-edit generated GraphQL client output under
  `src/planpilot/core/providers/github/github_gql/`.
- Keep scoped `AGENTS.md` files authoritative for their subtrees.

## Gates

- Run `poetry run poe check` before claiming code changes done.
- Run `poetry run poe test-e2e` for CLI flow changes.
- Run `poetry run poe docs-links` for docs changes.
- Run `poetry run poe workflow-lint` for workflow changes.
- Tests are offline; use fakes or mocks, never live GitHub calls.

## Repo Rules

- Preserve strict runtime typing; `disallow_untyped_defs = true`.
- Keep dry-run code paths network-free and side-effect-free.
- Validate external input at boundaries and handle errors explicitly.
- Update docs in the same change for user-visible behavior, config,
  architecture, provider, or CLI changes.
- Use Conventional Commit subjects for commits.
