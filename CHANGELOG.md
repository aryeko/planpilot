# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **Provider adapter pattern**: `Provider` ABC (`providers/base.py`) enabling future Jira/Linear integrations without touching the sync engine.
- **Async-first `SyncEngine`**: 5-phase pipeline (setup, discovery, upsert, enrich, relations) replaces the monolithic `run_sync()`.
- **Pydantic models**: declarative schema validation for `Plan`, `Epic`, `Story`, `Task`, `SyncMap`, and all provider-side context models.
- **`BodyRenderer` Protocol**: rendering decoupled from sync logic; `MarkdownRenderer` is the default, swappable per-provider.
- **Async `GhClient`**: wraps `gh` CLI via `asyncio.create_subprocess_exec` with structured error handling.
- **Custom exception hierarchy**: `PlanPilotError` base with `PlanLoadError`, `PlanValidationError`, `AuthenticationError`, `ProviderError`, `ProjectURLError`, `SyncError`.
- **Standard `logging`** module replaces module-level `_verbose`/`_dry_run` globals.
- **GraphQL constants**: all queries/mutations extracted to `providers/github/queries.py`.
- **`FieldValue` model validator**: enforces at most one value field populated.
- **Local commitlint**: `commitlint` Python package as dev dependency with `commit-msg` git hook (`scripts/install-hooks.sh`).
- **`.python-version`**: pins pyenv local to 3.13.0.
- 194 tests at 91%+ branch coverage mirroring the source structure.

### Changed
- **`--size-from-tshirt true/false`** replaced with **`--no-size-from-tshirt`** flag (enabled by default).
- `SyncConfig` is now a Pydantic `BaseModel` (was a plain namespace).
- Loader raises `PlanLoadError` instead of `RuntimeError` for file/JSON errors.
- CLI only catches `PlanPilotError` (narrower than previous `RuntimeError` catch).
- `graphql()` variables type hint widened from `dict[str, str]` to `dict[str, Any]`.
- `build_parent_map` / `build_blocked_by_map` skip nodes without valid IDs.
- Provider label creation uses narrower exception handling with type info.
- Validator docstring documents the single-epic constraint.

### Removed
- `run_sync()` function -- replaced by `SyncEngine.sync()`.
- `types.py`, `github_api.py`, `body_render.py`, `utils.py`, `relations.py`, `project_fields.py`, `sync.py` (monolithic modules replaced by modular packages).

## [0.2.0] - Unreleased

### Changed
- Renamed project from `plan-gh-project-sync` to `planpilot`.
- Migrated build system from setuptools to Poetry.
- CLI command renamed from `plan-gh-project-sync` to `planpilot`.
- Added `planpilot-slice` as a standalone CLI entry point.
- Switched test runner to pytest.
- Added ruff for linting and formatting.
- Added mypy for type checking.
- Updated CI workflows with lint step and Poetry.
- Added PyPI publishing via Trusted Publisher (OIDC).
- Added TestPyPI workflow for pre-release validation.
- **Strict required-field validation**: all required fields on epics, stories, and tasks are now validated upfront with clear error messages.
- **Removed silent fallbacks**: missing `epic_id` on stories, missing `story_ids` on epics, and missing `task_ids` on stories now fail validation instead of guessing defaults.
- Removed confusing `story.get("story_ids")` fallback on stories (was a typo-based fallback for `task_ids`).

### Removed
- Removed `tools/` directory (functionality available via `planpilot-slice` CLI).

## [0.1.0] - 2026-02-08

### Added
- Initial extraction from internal skill-local tool.
- Installable package with console script.
- Dry-run/apply mode enforcement.
- Fast-fail preflight for missing inputs and `gh auth status` failures.
- Multi-epic slicing helper and tests.
- CI and release workflows.
- OSS baseline docs and governance files.
