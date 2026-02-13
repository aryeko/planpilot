"""Shared metadata parsing utilities."""

from __future__ import annotations

_META_START = "PLANPILOT_META_V1"
_META_END = "END_PLANPILOT_META"


def parse_metadata_block(body: str) -> dict[str, str]:
    """Extract key/value metadata from a PLANPILOT block."""
    lines = body.splitlines()
    try:
        start = lines.index(_META_START)
    except ValueError:
        return {}
    try:
        end = lines.index(_META_END, start + 1)
    except ValueError:
        return {}

    metadata: dict[str, str] = {}
    for line in lines[start + 1 : end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key:
            metadata[key] = value
    return metadata
