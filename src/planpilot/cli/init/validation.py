"""Init validation helpers."""

from __future__ import annotations

from planpilot.core.contracts.exceptions import ProjectURLError
from planpilot.core.targets.github_project import parse_project_url


def validate_board_url(value: str) -> bool:
    try:
        parse_project_url(value)
    except ProjectURLError:
        return False
    return True


__all__ = ["validate_board_url"]
