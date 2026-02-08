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

### Stricter validation (v0.2.0)

v0.2.0 enforces all required fields and removes silent fallbacks:

| What changed | Old behavior | New behavior |
|---|---|---|
| Missing `epic_id` on story | Fell back to first epic's ID | Validation error |
| Missing `story_ids` on epic | Used all stories in order | Validation error |
| Missing `task_ids` on story | Fell back to `story_ids` key (typo) | Validation error |
| Missing `goal`, `spec_ref`, etc. | Silent empty section in issue body | Validation error |

If your existing plan files relied on these fallbacks, add the missing fields before upgrading. See [schemas.md](schemas.md) for the full list of required fields.

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
