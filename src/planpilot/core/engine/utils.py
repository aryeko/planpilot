"""Engine utility helpers."""

from __future__ import annotations

from planpilot.core.contracts.plan import PlanItem, PlanItemType
from planpilot.core.metadata import parse_metadata_block as _parse_metadata_block


def parse_metadata_block(body: str) -> dict[str, str]:
    return _parse_metadata_block(body)


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
