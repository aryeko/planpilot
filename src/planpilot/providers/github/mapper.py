"""GitHub provider mapping utilities."""

from __future__ import annotations

import re

from planpilot.contracts.exceptions import ProjectURLError

_PROJECT_RE = re.compile(r"^https://github\.com/(orgs|users)/([^/]+)/projects/(\d+)/?$")


def parse_project_url(url: str) -> tuple[str, str, int]:
    match = _PROJECT_RE.match(url.strip())
    if match is None:
        raise ProjectURLError(f"Unsupported project URL: {url}")
    owner_segment, owner, project_number_text = match.groups()
    owner_type = "org" if owner_segment == "orgs" else "user"
    return owner_type, owner, int(project_number_text)


def resolve_option_id(options: list[dict[str, str]], name: str) -> str | None:
    lowered = name.strip().lower()
    if not lowered:
        return None
    for option in options:
        if option.get("name", "").strip().lower() == lowered:
            return option.get("id")
    return None


def build_parent_map(data: dict) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for node in data.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        parent = node.get("parent")
        if isinstance(node_id, str) and isinstance(parent, dict):
            parent_id = parent.get("id")
            if isinstance(parent_id, str):
                mapping[node_id] = parent_id
    return mapping


def build_blocked_by_map(data: dict) -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    for node in data.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        blocked_by = node.get("blockedBy")
        if not isinstance(node_id, str) or not isinstance(blocked_by, dict):
            continue
        blockers = {
            blocker_id
            for blocker in blocked_by.get("nodes", [])
            if isinstance(blocker, dict)
            for blocker_id in [blocker.get("id")]
            if isinstance(blocker_id, str)
        }
        if blockers:
            mapping[node_id] = blockers
    return mapping
