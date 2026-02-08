# Release Guide

## How releases work

planpilot uses [python-semantic-release](https://python-semantic-release.readthedocs.io/) for fully automated versioning and publishing. When commits are merged to `main`, the release workflow:

1. Analyzes commit messages using [Conventional Commits](https://www.conventionalcommits.org/)
2. Determines the next version (major/minor/patch) based on commit types
3. Bumps the version in `pyproject.toml` and `src/planpilot/__init__.py`
4. Updates `CHANGELOG.md`
5. Creates a git tag and GitHub Release
6. Publishes to PyPI via Trusted Publisher (OIDC)

**You never need to manually bump versions, tag, or publish.**

## Commit message conventions

Version bumps are determined by commit message prefixes:

| Prefix | Version bump | Example |
|--------|-------------|---------|
| `feat:` | Minor (0.x.0) | `feat: add Jira adapter` |
| `fix:` | Patch (0.0.x) | `fix: handle empty task_ids` |
| `perf:` | Patch (0.0.x) | `perf: reduce API calls during sync` |
| `BREAKING CHANGE:` | Major (x.0.0) | `feat!: require epic_id on stories` |
| `docs:`, `chore:`, `ci:`, `test:`, `refactor:`, `style:` | No release | `docs: update schema examples` |

Breaking changes can also be indicated with a `!` after the type (e.g. `feat!:`) or with a `BREAKING CHANGE:` footer in the commit body.

## Testing releases (TestPyPI)

Use the manual "Test Release" workflow in GitHub Actions:

1. Go to Actions > Test Release > Run workflow
2. Select a force bump type (defaults to `prerelease`)
3. The workflow builds and publishes to TestPyPI without tagging

Verify:

```bash
pip install -i https://test.pypi.org/simple/ planpilot
```

## Pre-release checks

Before merging a release-worthy PR:

```bash
poetry run pytest -v
poetry run ruff check .
poetry run ruff format --check .
poetry run planpilot --help
```

## Branch protection

The `main` branch is protected:

- PRs require at least 1 approving review
- All CI checks must pass (lint, tests, commitlint)
- Stale reviews are dismissed on new pushes
- Direct pushes to `main` are blocked

## Manual override

If you need to force a specific version bump, you can run semantic-release locally:

```bash
pip install python-semantic-release
semantic-release version --patch  # or --minor, --major
```

This is rarely needed since commit messages drive versioning automatically.
