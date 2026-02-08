# Changelog

All notable changes to this project will be documented in this file.

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
