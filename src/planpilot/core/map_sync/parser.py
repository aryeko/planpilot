"""Remote item parsing for map-sync workflows."""

from __future__ import annotations

import re

from planpilot.core.contracts.plan import PlanItem, PlanItemType


class RemotePlanParser:
    @staticmethod
    def resolve_remote_item_type(*, item_id: str, metadata: dict[str, str]) -> PlanItemType:
        raw = (metadata.get("ITEM_TYPE") or "").strip().upper()
        if raw in {"EPIC", "STORY", "TASK"}:
            return PlanItemType(raw)
        upper_item_id = item_id.upper()
        if upper_item_id.startswith("EPIC"):
            return PlanItemType.EPIC
        if upper_item_id.startswith("STORY"):
            return PlanItemType.STORY
        return PlanItemType.TASK

    @staticmethod
    def extract_markdown_sections(body: str) -> dict[str, str]:
        sections: dict[str, str] = {}
        current: str | None = None
        lines: list[str] = []
        for line in body.splitlines():
            if line.startswith("## "):
                if current is not None:
                    sections[current] = "\n".join(lines).strip()
                current = line[3:].strip()
                lines = []
                continue
            if current is not None:
                lines.append(line)
        if current is not None:
            sections[current] = "\n".join(lines).strip()
        return sections

    @staticmethod
    def parse_bullets(section: str | None) -> list[str]:
        if not section:
            return []
        values: list[str] = []
        for line in section.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            match = re.match(r"^[*-]\s+(.*)$", stripped)
            if match:
                values.append(match.group(1).strip())
            else:
                values.append(stripped)
        return values

    def plan_item_from_remote(self, *, item_id: str, metadata: dict[str, str], title: str, body: str) -> PlanItem:
        item_type = self.resolve_remote_item_type(item_id=item_id, metadata=metadata)
        sections = self.extract_markdown_sections(body)
        goal = sections.get("Goal")
        requirements = self.parse_bullets(sections.get("Requirements"))
        acceptance = self.parse_bullets(sections.get("Acceptance Criteria"))

        if not goal:
            goal = "(migrated from remote)"
        if not requirements:
            requirements = ["(migrated from remote)"]
        if not acceptance:
            acceptance = ["(migrated from remote)"]

        return PlanItem(
            id=item_id,
            type=item_type,
            title=title,
            goal=goal,
            parent_id=(metadata.get("PARENT_ID") or None),
            requirements=requirements,
            acceptance_criteria=acceptance,
        )
