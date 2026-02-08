# Migration from skill-local module

If you previously invoked the tool via skill-local path:

```bash
PYTHONPATH="/path/to/skills/plan-to-github-project/plan_gh_project_sync/src" python3 -m plan_gh_project_sync ...
```

Move to repository-local usage:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/plan-gh-project-sync --help
```

This repo keeps the same module name (`plan_gh_project_sync`) while providing a stable console entrypoint.
