# Migration Guide

## From plan-gh-project-sync to planpilot

### Package rename

The project was renamed from `plan-gh-project-sync` to `planpilot` in v0.2.0.

| What | Old | New |
|------|-----|-----|
| PyPI package | `plan-gh-project-sync` | `planpilot` |
| Python import | `plan_gh_project_sync` | `planpilot` |
| CLI command | `plan-gh-project-sync` | `planpilot` |
| Module run | `python -m plan_gh_project_sync` | `python -m planpilot` |

### Install the new package

```bash
pip install planpilot
# or
poetry add planpilot
```

### Update CLI invocations

```bash
# Old
plan-gh-project-sync --repo owner/repo --project-url ... --dry-run

# New
planpilot --repo owner/repo --project-url ... --dry-run
```

### Slicing helper

The `tools/slice_epics_for_sync.py` script has been replaced with a proper CLI entry point:

```bash
# Old
PYTHONPATH=src python3 tools/slice_epics_for_sync.py --epics-path ...

# New
planpilot-slice --epics-path ...
```

## From skill-local module (pre-v0.1.0)

If you previously invoked the tool via skill-local path:

```bash
PYTHONPATH="/path/to/skills/plan-to-github-project/plan_gh_project_sync/src" python3 -m plan_gh_project_sync ...
```

Install the package instead:

```bash
pip install planpilot
planpilot --help
```
