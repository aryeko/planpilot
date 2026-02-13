"""Init validation helpers."""

from __future__ import annotations

from planpilot import validate_board_url as _validate_board_url


def validate_board_url(value: str) -> bool:
    return _validate_board_url(value)


__all__ = ["validate_board_url"]
