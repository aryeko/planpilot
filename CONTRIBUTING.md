# Contributing

## Setup

```bash
# Install Poetry if you don't have it
curl -sSL https://install.python-poetry.org | python3 -

# Clone and install
git clone https://github.com/aryeko/planpilot.git
cd planpilot
poetry install
```

## Development

```bash
# Run tests
poetry run pytest -v

# Lint
poetry run ruff check .

# Format
poetry run ruff format .

# Verify CLI
poetry run planpilot --help
```

## Pull requests

- Keep changes focused and well-tested.
- Include rationale and verification steps.
- Ensure `ruff check` and `ruff format --check` pass.
- Prefer dry-run examples in docs for sync operations.
