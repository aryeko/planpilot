from __future__ import annotations

import pytest

from planpilot.core.contracts.exceptions import PlanValidationError
from planpilot.core.contracts.plan import Plan, PlanItem, PlanItemType
from planpilot.core.plan.validator import PlanValidator


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
    plan = Plan(items=[_item("DUP", PlanItemType.EPIC), _item("DUP", PlanItemType.EPIC)])

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
            _item("E1", PlanItemType.EPIC),
            _item("S1", PlanItemType.STORY, parent_id="E1"),
        ]
    )

    with pytest.raises(PlanValidationError):
        PlanValidator().validate(plan)


def test_strict_mode_missing_dependency_reference_fails() -> None:
    plan = Plan(items=[_item("E1", PlanItemType.EPIC, depends_on=["E404"])])

    with pytest.raises(PlanValidationError):
        PlanValidator().validate(plan, mode="strict")


def test_partial_mode_missing_dependency_reference_is_allowed() -> None:
    plan = Plan(items=[_item("E1", PlanItemType.EPIC, depends_on=["E404"])])

    PlanValidator().validate(plan, mode="partial")


def test_invalid_mode_fails_validation() -> None:
    plan = Plan(items=[_item("E1", PlanItemType.EPIC)])

    with pytest.raises(PlanValidationError, match="invalid validation mode"):
        PlanValidator().validate(plan, mode="unsupported")


def test_story_parent_must_be_epic() -> None:
    plan = Plan(
        items=[
            _item("S1", PlanItemType.STORY, parent_id="S2"),
            _item("S2", PlanItemType.STORY),
        ]
    )

    with pytest.raises(PlanValidationError, match="story parent must be epic"):
        PlanValidator().validate(plan)


def test_invalid_type_reports_error() -> None:
    malformed = PlanItem.model_construct(
        id="BAD",
        type="INVALID",
        title="Bad",
        goal="Goal",
        requirements=["R"],
        acceptance_criteria=["A"],
    )
    plan = Plan.model_construct(items=[malformed])

    with pytest.raises(PlanValidationError, match="invalid type"):
        PlanValidator().validate(plan)


def test_sub_item_parent_mismatch_is_reported() -> None:
    plan = Plan(
        items=[
            _item("E1", PlanItemType.EPIC, sub_item_ids=["S1"]),
            _item("S1", PlanItemType.STORY, parent_id="E2"),
            _item("E2", PlanItemType.EPIC, sub_item_ids=["S1"]),
        ]
    )

    with pytest.raises(PlanValidationError, match="sub-item parent mismatch"):
        PlanValidator().validate(plan)


def test_sub_item_consistency_passes_with_inverse_present() -> None:
    plan = Plan(
        items=[
            _item("E1", PlanItemType.EPIC, sub_item_ids=["S1"]),
            _item("S1", PlanItemType.STORY, parent_id="E1"),
        ]
    )

    PlanValidator().validate(plan)


def test_strict_mode_allows_loaded_dependency_reference() -> None:
    plan = Plan(
        items=[
            _item("E1", PlanItemType.EPIC, depends_on=["E2"]),
            _item("E2", PlanItemType.EPIC),
        ]
    )

    PlanValidator().validate(plan, mode="strict")
