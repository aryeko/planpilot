"""Shared discovery utilities for finding and categorizing existing items.

This module handles marker parsing and item categorization -- planpilot-specific,
not provider-specific.
"""

from __future__ import annotations

def parse_markers(body: str) -> dict[str, str]:
    """Extract plan markers from an item body.

    Markers are HTML comments like ``<!-- PLAN_ID: abc123 -->``.

    Args:
        body: Item body text

    Returns:
        Dict with keys: plan_id, epic_id, story_id, task_id (empty string if absent).
    """

    def _extract(label: str) -> str:
        token = f"<!-- {label}:"
        start = body.find(token)
        if start == -1:
            return ""
        # Find the closing --> for this marker
        end = body.find("-->", start)
        if end == -1:
            return ""
        # Check if there's another <!-- marker before the closing -->
        # If so, this marker is malformed
        next_marker = body.find("<!--", start + len(token), end)
        if next_marker != -1:
            return ""
        return body[start + len(token) : end].strip()

    return {
        "plan_id": _extract("PLAN_ID"),
        "epic_id": _extract("EPIC_ID"),
        "story_id": _extract("STORY_ID"),
        "task_id": _extract("TASK_ID"),
    }
