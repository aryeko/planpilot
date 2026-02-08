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
