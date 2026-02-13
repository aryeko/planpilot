# Documentation Ownership Refresh Plan (2026-02-13)

## Goal

Bring all user-facing and contributor-facing documentation in sync with the finalized runtime ownership model:

- `src/planpilot/core/*` owns runtime domains (auth, config, contracts, engine, plan, providers, renderers, targets)
- `src/planpilot/cli/*` owns command parsing/execution, persistence helpers, and init UX
- `src/planpilot/sdk.py` remains the SDK composition root and public programmatic entrypoint

Also improve OSS readability with clearer architecture visuals and a dedicated repository layout reference.

## Scope

1. Update stale architecture references in root docs:
   - `AGENTS.md`
   - `CONTRIBUTING.md`

2. Update docs index and architecture pages:
   - `docs/README.md`
   - `docs/design/architecture.md`

3. Refresh module specs to match current paths and API boundaries:
   - `docs/modules/cli.md`
   - `docs/modules/sdk.md`
   - `docs/modules/config.md`
   - `docs/modules/auth.md`
   - `docs/modules/providers.md`
   - `docs/modules/github-provider.md`
   - `docs/modules/plan.md`
   - `docs/modules/renderers.md`

4. Add one new high-signal design doc for contributors:
   - `docs/design/repository-layout.md`

## Diagram Additions (Mermaid)

- Keep and update architecture dependency diagram in `docs/design/architecture.md`.
- Add a new repository map and ownership diagram in `docs/design/repository-layout.md`.
- Ensure command flow in CLI spec stays accurate with package-based CLI structure.

## Quality Bar

- No stale references to removed legacy paths like `src/planpilot/config/*`, `src/planpilot/providers/*`, or `src/planpilot/cli.py`.
- Docs must describe actual import boundaries used in code/tests.
- Verify with:
  - `poetry run poe check`
  - `poetry run pytest tests/e2e/test_cli_e2e.py`

## Deliverables

- Updated docs aligned to current source tree.
- New repository layout doc with mermaid visuals.
- One documentation commit with clear breaking-layout rationale.
