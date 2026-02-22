---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Hooks

> This file extends [common/hooks.md](../common/hooks.md) with Python-specific content.

## PostToolUse Hooks

Configure in `~/.claude/settings.json`:

- **ruff format**: Auto-format `.py` files after edit
- **mypy**: Run type checking after editing `.py` files

## Warnings

- Warn about `print()` statements in edited files (use `logging` module instead)
