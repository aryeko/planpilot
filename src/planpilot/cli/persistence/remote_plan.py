"""Remote-plan persistence helpers for map-sync workflows."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from planpilot.core.contracts.exceptions import SyncError
from planpilot.core.contracts.plan import PlanItem, PlanItemType


class RemotePlanPersistence:
    @staticmethod
    def plan_type_rank(item_type: PlanItemType) -> int:
        if item_type is PlanItemType.EPIC:
            return 0
        if item_type is PlanItemType.STORY:
            return 1
        return 2

    def persist_plan_from_remote(self, *, items: Iterable[PlanItem], plan_paths: Any) -> None:
        ordered = sorted(
            items,
            key=lambda item: (
                self.plan_type_rank(item.type),
                item.id,
            ),
        )
        by_parent: dict[str, list[str]] = {}
        for item in ordered:
            if item.parent_id:
                by_parent.setdefault(item.parent_id, []).append(item.id)
        normalized: list[PlanItem] = []
        for item in ordered:
            normalized.append(item.model_copy(update={"sub_item_ids": sorted(by_parent.get(item.id, []))}))

        try:
            if plan_paths.unified is not None:
                path = plan_paths.unified
                path.parent.mkdir(parents=True, exist_ok=True)
                payload = {"items": [item.model_dump(mode="json", exclude_none=True) for item in normalized]}
                path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
                return

            split: dict[PlanItemType, list[dict[str, Any]]] = {
                PlanItemType.EPIC: [],
                PlanItemType.STORY: [],
                PlanItemType.TASK: [],
            }
            for item in normalized:
                split[item.type].append(item.model_dump(mode="json", exclude_none=True))

            for item_type, maybe_path in (
                (PlanItemType.EPIC, plan_paths.epics),
                (PlanItemType.STORY, plan_paths.stories),
                (PlanItemType.TASK, plan_paths.tasks),
            ):
                if maybe_path is None:
                    continue
                path = maybe_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(split[item_type], indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            raise SyncError("failed to persist plan files from remote map sync") from exc


def persist_plan_from_remote(*, items: Iterable[PlanItem], plan_paths: Any) -> None:
    RemotePlanPersistence().persist_plan_from_remote(items=items, plan_paths=plan_paths)


__all__ = ["RemotePlanPersistence", "persist_plan_from_remote"]
