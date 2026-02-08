# Release Guide

## Pre-release checks

```bash
poetry run pytest -v
poetry run ruff check .
poetry run planpilot --help
```

## Test release (TestPyPI)

```bash
git tag v0.2.0-rc1
git push origin v0.2.0-rc1
```

The `test-release.yml` workflow builds and publishes to TestPyPI.

Verify:

```bash
pip install -i https://test.pypi.org/simple/ planpilot
```

## Production release (PyPI)

```bash
git tag v0.2.0
git push origin v0.2.0
```

The `release.yml` workflow builds, tests, and publishes to PyPI via Trusted Publisher.

## Version bump

Update the version in `pyproject.toml` and `src/planpilot/__init__.py`:

```bash
poetry version <major|minor|patch>
```

Then update `__version__` in `src/planpilot/__init__.py` to match.
