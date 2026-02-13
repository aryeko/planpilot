"""Shared CLI formatting helpers."""

from __future__ import annotations


def format_comma_or_none(values: list[str]) -> str:
    if not values:
        return "none"
    return ", ".join(values)


def format_type_breakdown(*, epics: int, stories: int, tasks: int) -> str:
    parts: list[str] = []
    if epics:
        parts.append(f"{epics} epic{'s' if epics != 1 else ''}")
    if stories:
        parts.append(f"{stories} stor{'ies' if stories != 1 else 'y'}")
    if tasks:
        parts.append(f"{tasks} task{'s' if tasks != 1 else ''}")
    return ", ".join(parts) if parts else "none"
