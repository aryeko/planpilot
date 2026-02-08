# Contributing

## Setup

```bash
# Install Poetry if you don't have it
curl -sSL https://install.python-poetry.org | python3 -

# Clone and install
git clone https://github.com/aryeko/planpilot.git
cd planpilot
poetry install

# Install git hooks (commit-msg linting)
./scripts/install-hooks.sh
```

## Development

Development tasks are managed with [poethepoet](https://github.com/nat-n/poethepoet). Run any task with `poe <task>` (or `poetry run poe <task>` if poe is not on your PATH):

| Command | Description |
|---------|-------------|
| `poe lint` | Run ruff linter (`ruff check .`) |
| `poe format` | Auto-format code (`ruff format .`) |
| `poe format-check` | Check formatting without changes (`ruff format --check .`) |
| `poe test` | Run tests with verbose output (`pytest -v`) |
| `poe coverage` | Run tests and generate HTML coverage report |
| `poe typecheck` | Run mypy type-checking (`mypy src/planpilot`) |
| `poe check` | Run lint + format-check + tests in sequence |

```bash
# Quick check before pushing
poe check

# Verify CLI
poetry run planpilot --help
```

## Architecture

planpilot follows SOLID principles with a modular, provider-agnostic design:

- **`models/`** -- Pydantic domain models (`Plan`, `Epic`, `Story`, `Task`, `SyncMap`, …)
- **`plan/`** -- Plan loading from JSON, relational validation, deterministic hashing
- **`providers/`** -- `Provider` ABC defining the adapter interface; `github/` implements it using the `gh` CLI
- **`rendering/`** -- `BodyRenderer` Protocol for issue body generation; `MarkdownRenderer` is the default
- **`sync/`** -- `SyncEngine` orchestrates the 5-phase sync pipeline, depends only on `Provider` and `BodyRenderer` abstractions
- **`config.py`** -- Pydantic `SyncConfig` built from CLI arguments
- **`exceptions.py`** -- Custom exception hierarchy (`PlanPilotError` → specific errors)

To add a new provider (e.g. Jira), implement the `Provider` ABC in `providers/jira/` -- no changes to the sync engine needed.

## Commit messages

We use [Conventional Commits](https://www.conventionalcommits.org/) to drive automated versioning and changelog generation. All commits must follow this format:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

Common types:

| Type | Purpose | Version bump |
|------|---------|-------------|
| `feat` | New feature | Minor |
| `fix` | Bug fix | Patch |
| `docs` | Documentation only | None |
| `chore` | Maintenance / tooling | None |
| `test` | Adding or updating tests | None |
| `refactor` | Code change that neither fixes nor adds | None |
| `perf` | Performance improvement | Patch |
| `ci` | CI/CD changes | None |

Breaking changes: add `!` after the type (e.g. `feat!: remove fallback`) or include a `BREAKING CHANGE:` footer.

**Header limit**: 72 characters maximum (enforced by CI and the local hook).

Commit messages are linted in CI via [commitlint](https://github.com/opensource-nepal/commitlint) and locally via a `commit-msg` git hook. The same `commitlint` package is included as a dev dependency (`poetry install`). Run `./scripts/install-hooks.sh` to install the hook.

## Pull requests

```mermaid
flowchart LR
    A[Branch] --> B[Commit with\nConventional Commits]
    B --> C[Push & open PR]
    C --> D{CI checks}
    D -->|commitlint| D1[Commit format ✓]
    D -->|ruff| D2[Lint + format ✓]
    D -->|pytest| D3[Tests ✓]
    D1 & D2 & D3 --> E[Review & approve]
    E --> F[Merge to main]
    F --> G[Auto-release\nif feat:/fix:]
```

- Keep changes focused and well-tested.
- Use Conventional Commit format for all commits (enforced by CI).
- Include rationale and verification steps.
- Ensure `poe check` passes (lint + format + tests).
- PRs require at least 1 approving review and all CI checks to pass.
- Prefer dry-run examples in docs for sync operations.

## Test structure

Tests mirror the source layout under `tests/`:
