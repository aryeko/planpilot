"""Engine utility helpers."""

from __future__ import annotations

from planpilot_v2.contracts.plan import PlanItem, PlanItemType

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


def compute_parent_blocked_by(items: list[PlanItem], item_type: PlanItemType) -> set[tuple[str, str]]:
    """Compute parent-level blocked-by edges from child dependency edges."""
    if item_type == PlanItemType.STORY:
        child_type = PlanItemType.TASK
    elif item_type == PlanItemType.EPIC:
        child_type = PlanItemType.STORY
    else:
        return set()

    by_id = {item.id: item for item in items}
    edges: set[tuple[str, str]] = set()

    for item in items:
        if item.type != child_type or not item.parent_id:
            continue
        for dep_id in item.depends_on:
            dep = by_id.get(dep_id)
            if dep is None or dep.type != child_type or not dep.parent_id:
                continue
            if dep.parent_id == item.parent_id:
                continue
            edges.add((item.parent_id, dep.parent_id))

    return edges
