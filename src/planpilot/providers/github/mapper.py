"""Mapping functions between GitHub API responses and domain models."""

from __future__ import annotations

import re
from typing import Any

from planpilot.exceptions import ProjectURLError

# Regex for project URL: https://github.com/orgs/{org}/projects/{number}
_PROJECT_URL_RE = re.compile(r"https://github\.com/orgs/([^/]+)/projects/(\d+)/?$")


def parse_project_url(url: str) -> tuple[str, int]:
    """Parse a GitHub project URL into (org, number).

    Args:
        url: Full GitHub project URL.

    Returns:
        Tuple of (organization, project_number).

    Raises:
        ProjectURLError: If the URL format is invalid.
    """
    m = _PROJECT_URL_RE.match(url)
    if not m:
        raise ProjectURLError(
            f"Invalid project URL: {url!r}. "
            "Expected format: https://github.com/orgs/{{org}}/projects/{{number}}"
        )
    return m.group(1), int(m.group(2))


def parse_markers(body: str) -> dict[str, str]:
    """Extract plan markers from an issue body.

    Markers are HTML comments like ``<!-- PLAN_ID: abc123 -->``.

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


def build_issue_mapping(
    issues: list[dict[str, Any]],
    plan_id: str = "",
) -> dict[str, dict[str, dict[str, Any]]]:
    """Build a mapping of entity IDs to issue metadata, filtered by plan_id.

    Args:
        issues: Raw issue dicts from the search API.
        plan_id: Only include issues matching this plan_id.

    Returns:
        Nested dict: ``{"epics": {id: {id, number}}, "stories": ..., "tasks": ...}``.
    """
    mapping: dict[str, dict[str, dict[str, Any]]] = {"epics": {}, "stories": {}, "tasks": {}}
    for issue in issues:
        markers = parse_markers(issue.get("body", ""))
        if plan_id and markers.get("plan_id") != plan_id:
            continue
        entry = {"id": issue.get("id"), "number": issue.get("number")}
        if markers.get("epic_id"):
            mapping["epics"][markers["epic_id"]] = entry
        if markers.get("story_id"):
            mapping["stories"][markers["story_id"]] = entry
        if markers.get("task_id"):
            mapping["tasks"][markers["task_id"]] = entry
    return mapping


def build_project_item_map(items: list[dict[str, Any]]) -> dict[str, str]:
    """Build a mapping of issue node-ID to project item-ID.

    Args:
        items: Raw project-item nodes from the API.

    Returns:
        Dict mapping content (issue) ID to project-item ID.
    """
    cache: dict[str, str] = {}
    for item in items:
        content = item.get("content") or {}
        content_id = content.get("id")
        if content_id and item.get("id"):
            cache[content_id] = item["id"]
    return cache


def resolve_option_id(options: list[dict[str, str]], name: str | None) -> str | None:
    """Find the option ID matching *name* (case-insensitive).

    Args:
        options: List of ``{"id": ..., "name": ...}`` dicts.
        name: Option name to search for.

    Returns:
        The matching option ID, or None.
    """
    if not name:
        return None
    lower = name.lower()
    for opt in options:
        if opt.get("name", "").lower() == lower:
            return opt.get("id")
    return None


def build_parent_map(nodes: list[dict[str, Any]]) -> dict[str, str | None]:
    """Build a mapping of issue ID to parent issue ID.

    Args:
        nodes: Issue nodes with optional ``parent`` field.

    Returns:
        Dict mapping issue ID to parent ID (or None).
    """
    mapping: dict[str, str | None] = {}
    for node in nodes:
        parent = node.get("parent")
        mapping[node.get("id", "")] = parent.get("id") if parent else None
    return mapping


def build_blocked_by_map(nodes: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Build a mapping of issue ID to set of blocking issue IDs.

    Args:
        nodes: Issue nodes with ``blockedBy`` field.

    Returns:
        Dict mapping issue ID to set of blocker IDs.
    """
    mapping: dict[str, set[str]] = {}
    for node in nodes:
        blocked = node.get("blockedBy", {}).get("nodes", [])
        mapping[node.get("id", "")] = {n.get("id") for n in blocked if n.get("id")}
    return mapping
