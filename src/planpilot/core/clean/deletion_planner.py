"""Deletion ordering for clean workflows."""

from __future__ import annotations

from planpilot.core.contracts.item import Item
from planpilot.core.contracts.plan import Plan, PlanItemType


class CleanDeletionPlanner:
    @staticmethod
    def item_type_rank(item_type: PlanItemType | str | None) -> int:
        if item_type in {PlanItemType.TASK, "TASK"}:
            return 0
        if item_type in {PlanItemType.STORY, "STORY"}:
            return 1
        if item_type in {PlanItemType.EPIC, "EPIC"}:
            return 2
        return 3

    def order_items_for_deletion(
        self,
        items: list[Item],
        *,
        metadata_by_provider_id: dict[str, dict[str, str]],
        plan: Plan | None,
        all_plans: bool,
    ) -> list[Item]:
        if not items:
            return []

        item_by_provider_id = {item.id: item for item in items}
        plan_items_by_id = {plan_item.id: plan_item for plan_item in (plan.items if plan is not None else [])}
        provider_id_by_item_id: dict[str, str] = {}
        plan_type_by_provider_id: dict[str, PlanItemType] = {}

        for item in items:
            metadata = metadata_by_provider_id.get(item.id, {})
            item_id = metadata.get("ITEM_ID")
            if not item_id:
                continue
            provider_id_by_item_id[item_id] = item.id
            plan_item = plan_items_by_id.get(item_id)
            if plan_item is not None:
                plan_type_by_provider_id[item.id] = plan_item.type

        prerequisites: dict[str, set[str]] = {item.id: set() for item in items}
        dependents: dict[str, set[str]] = {item.id: set() for item in items}

        for item in items:
            metadata = metadata_by_provider_id.get(item.id, {})
            item_id = metadata.get("ITEM_ID")
            parent_item_id: str | None = None

            if all_plans:
                parent_item_id = metadata.get("PARENT_ID")
            elif item_id:
                plan_item = plan_items_by_id.get(item_id)
                parent_item_id = plan_item.parent_id if plan_item is not None else None

            if not parent_item_id:
                continue

            parent_provider_id = provider_id_by_item_id.get(parent_item_id)
            if parent_provider_id is None or parent_provider_id == item.id:
                continue

            prerequisites[parent_provider_id].add(item.id)
            dependents[item.id].add(parent_provider_id)

        def sort_key(provider_id: str) -> tuple[int, str, str]:
            item = item_by_provider_id[provider_id]
            metadata = metadata_by_provider_id.get(provider_id, {})
            type_hint: PlanItemType | str | None = (
                plan_type_by_provider_id.get(provider_id) or metadata.get("ITEM_TYPE") or item.item_type
            )
            return (self.item_type_rank(type_hint), item.key, item.id)

        remaining_prereqs = {provider_id: set(reqs) for provider_id, reqs in prerequisites.items()}
        ready = sorted(
            [provider_id for provider_id, reqs in remaining_prereqs.items() if not reqs],
            key=sort_key,
        )
        ordered: list[str] = []

        while ready:
            current = ready.pop(0)
            ordered.append(current)
            for parent in sorted(dependents[current], key=sort_key):
                prereq_set = remaining_prereqs[parent]
                if current in prereq_set:
                    prereq_set.remove(current)
                    if not prereq_set:
                        ready.append(parent)
            ready.sort(key=sort_key)

        if len(ordered) != len(items):
            remaining = [provider_id for provider_id in item_by_provider_id if provider_id not in set(ordered)]
            ordered.extend(sorted(remaining, key=sort_key))

        return [item_by_provider_id[provider_id] for provider_id in ordered]
