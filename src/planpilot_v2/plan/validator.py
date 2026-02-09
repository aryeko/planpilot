"""Plan relational validation."""

from __future__ import annotations

from collections import Counter

from planpilot_v2.contracts.exceptions import PlanValidationError
from planpilot_v2.contracts.plan import Plan, PlanItem, PlanItemType


class PlanValidator:
    """Validate semantic integrity of a loaded Plan."""

    def validate(self, plan: Plan, *, mode: str = "strict") -> None:
        if mode not in {"strict", "partial"}:
            raise PlanValidationError(f"invalid validation mode: {mode}")

        errors: list[str] = []
        items_by_id = self._index_items(plan, errors)

        for item in plan.items:
            self._validate_type(item, errors)
            self._validate_required_fields(item, errors)
            self._validate_parent_and_hierarchy(item, items_by_id, mode=mode, errors=errors)
            self._validate_dependencies(item, items_by_id, mode=mode, errors=errors)
            self._validate_sub_item_consistency(item, items_by_id, errors)

        if errors:
            raise PlanValidationError("\n".join(errors))

    @staticmethod
    def _index_items(plan: Plan, errors: list[str]) -> dict[str, PlanItem]:
        counts = Counter(item.id for item in plan.items)
        for item_id, count in counts.items():
            if count > 1:
                errors.append(f"duplicate item id: {item_id}")
        return {item.id: item for item in plan.items}

    @staticmethod
    def _validate_type(item: PlanItem, errors: list[str]) -> None:
        if not isinstance(item.type, PlanItemType):
            errors.append(f"invalid type for {item.id}: {item.type!r}")

    @staticmethod
    def _validate_required_fields(item: PlanItem, errors: list[str]) -> None:
        if item.type is PlanItemType.EPIC and item.parent_id is not None:
            errors.append(f"epic cannot have parent_id: {item.id}")
        if not item.goal or not item.goal.strip():
            errors.append(f"missing required goal: {item.id}")
        if not item.requirements:
            errors.append(f"missing required requirements: {item.id}")
        if not item.acceptance_criteria:
            errors.append(f"missing required acceptance_criteria: {item.id}")

    def _validate_parent_and_hierarchy(
        self,
        item: PlanItem,
        items_by_id: dict[str, PlanItem],
        *,
        mode: str,
        errors: list[str],
    ) -> None:
        if item.parent_id is None:
            return

        parent = items_by_id.get(item.parent_id)
        if parent is None:
            if mode == "strict":
                errors.append(f"missing parent reference: {item.id} -> {item.parent_id}")
            return

        if item.type is PlanItemType.STORY and parent.type is not PlanItemType.EPIC:
            errors.append(f"story parent must be epic: {item.id} -> {item.parent_id}")
        if item.type is PlanItemType.TASK and parent.type is not PlanItemType.STORY:
            errors.append(f"task parent must be story: {item.id} -> {item.parent_id}")

    @staticmethod
    def _validate_dependencies(
        item: PlanItem,
        items_by_id: dict[str, PlanItem],
        *,
        mode: str,
        errors: list[str],
    ) -> None:
        for dep_id in item.depends_on:
            if dep_id in items_by_id:
                continue
            if mode == "strict":
                errors.append(f"missing dependency reference: {item.id} -> {dep_id}")

    @staticmethod
    def _validate_sub_item_consistency(item: PlanItem, items_by_id: dict[str, PlanItem], errors: list[str]) -> None:
        for sub_item_id in item.sub_item_ids:
            sub_item = items_by_id.get(sub_item_id)
            if sub_item is None:
                continue
            if sub_item.parent_id != item.id:
                errors.append(f"sub-item parent mismatch: {item.id} -> {sub_item_id}")

        if item.parent_id is None:
            return
        parent = items_by_id.get(item.parent_id)
        if parent is None:
            return
        if item.id not in parent.sub_item_ids:
            errors.append(f"parent missing sub_item_ids inverse: {item.id} -> {item.parent_id}")
