---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Coding Style

> This file extends [common/coding-style.md](../common/coding-style.md) with Python-specific content.

## Standards

- Follow **PEP 8** conventions
- Use **type annotations** on all function signatures

## Immutability

Prefer immutable data structures:

**Frozen dataclass:**
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class User:
    name: str
    email: str
```

**NamedTuple:**
```python
from typing import NamedTuple

class Point(NamedTuple):
    x: float
    y: float
```

## Formatting

- **ruff format** for code formatting
- **ruff check** for linting and import sorting

## Reference

See skill: `python-patterns` for comprehensive Python idioms and patterns.
