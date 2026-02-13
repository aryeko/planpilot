"""GitHub project URL parsing utilities."""

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
