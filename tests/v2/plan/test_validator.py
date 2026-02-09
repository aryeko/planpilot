from __future__ import annotations

import pytest

from planpilot_v2.contracts.exceptions import PlanValidationError
from planpilot_v2.contracts.plan import Plan, PlanItem, PlanItemType
from planpilot_v2.plan.validator import PlanValidator


def _item(
    item_id: str,
    item_type: PlanItemType,
    *,
    parent_id: str | None = None,
    sub_item_ids: list[str] | None = None,
    depends_on: list[str] | None = None,
    goal: str | None = "Goal",
    requirements: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
) -> PlanItem:
    return PlanItem(
        id=item_id,
        type=item_type,
        title=f"Title {item_id}",
        goal=goal,
        parent_id=parent_id,
        sub_item_ids=sub_item_ids or [],
        depends_on=depends_on or [],
        requirements=requirements if requirements is not None else ["R1"],
        acceptance_criteria=acceptance_criteria if acceptance_criteria is not None else ["AC1"],
    )


def test_duplicate_ids_fail_validation() -> None:
    plan = Plan(items=[_item("DUP", PlanItemType.EPIC), _item("DUP", PlanItemType.STORY, parent_id="E1")])

    with pytest.raises(PlanValidationError):
        PlanValidator().validate(plan)


def test_invalid_parent_type_fails_validation() -> None:
    plan = Plan(
        items=[
            _item("T1", PlanItemType.TASK, parent_id="T2"),
            _item("T2", PlanItemType.TASK),
        ]
    )

    with pytest.raises(PlanValidationError):
        PlanValidator().validate(plan)


def test_strict_mode_missing_reference_fails() -> None:
    plan = Plan(items=[_item("S1", PlanItemType.STORY, parent_id="E404")])

    with pytest.raises(PlanValidationError):
        PlanValidator().validate(plan, mode="strict")


def test_partial_mode_missing_reference_is_allowed() -> None:
    plan = Plan(items=[_item("S1", PlanItemType.STORY, parent_id="E404")])

    PlanValidator().validate(plan, mode="partial")


def test_epic_with_parent_id_fails_validation() -> None:
    plan = Plan(items=[_item("E1", PlanItemType.EPIC, parent_id="E0")])

    with pytest.raises(PlanValidationError):
        PlanValidator().validate(plan)


def test_missing_required_fields_fail_validation() -> None:
    plan = Plan(
        items=[
            _item(
                "T1",
                PlanItemType.TASK,
                goal=None,
                requirements=[],
                acceptance_criteria=[],
            )
        ]
    )

    with pytest.raises(PlanValidationError):
        PlanValidator().validate(plan)


def test_sub_item_consistency_fails_when_parent_inverse_missing() -> None:
    plan = Plan(
        items=[
            _item("E1", PlanItemType.EPIC, sub_item_ids=["S1"]),
            _item("S1", PlanItemType.STORY, parent_id="E2"),
        ]
    )

    with pytest.raises(PlanValidationError):
        PlanValidator().validate(plan)
