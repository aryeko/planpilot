# Contributing

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

## Run checks

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"
PYTHONPATH=src python3 -m plan_gh_project_sync --help
```

## Pull requests

- Keep changes focused and well-tested.
- Include rationale and verification steps.
- Prefer dry-run examples in docs for sync operations.
