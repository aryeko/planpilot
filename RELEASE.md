# Release Guide

## Tag release

```bash
git tag v0.1.0
git push origin v0.1.0
```

The `release.yml` workflow builds distribution artifacts on tag push.

## Pre-release checks

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"
PYTHONPATH=src python3 -m plan_gh_project_sync --help
```
