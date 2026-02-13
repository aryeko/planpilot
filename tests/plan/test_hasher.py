from __future__ import annotations

import re

from planpilot.core.contracts.plan import Plan, PlanItem, PlanItemType, Scope, Verification
from planpilot.core.plan.hasher import PlanHasher


def _plan_items_in_default_order() -> list[PlanItem]:
    return [
        PlanItem(
            id="E1",
            type=PlanItemType.EPIC,
            title="Epic",
            goal="Goal",
            requirements=["R1"],
            acceptance_criteria=["AC1"],
        ),
        PlanItem(
            id="S1",
            type=PlanItemType.STORY,
            title="Story",
            goal="Goal",
            parent_id="E1",
            requirements=["R1"],
            acceptance_criteria=["AC1"],
        ),
    ]


def test_hash_is_deterministic() -> None:
    plan = Plan(items=_plan_items_in_default_order())

    hasher = PlanHasher()
    first = hasher.compute_plan_id(plan)
    second = hasher.compute_plan_id(plan)

    assert first == second


def test_hash_is_stable_when_items_reordered() -> None:
    hasher = PlanHasher()
    ordered = Plan(items=_plan_items_in_default_order())
    reordered = Plan(items=list(reversed(_plan_items_in_default_order())))

    assert hasher.compute_plan_id(ordered) == hasher.compute_plan_id(reordered)


def test_hash_changes_for_semantically_different_plan() -> None:
    hasher = PlanHasher()
    left = Plan(items=_plan_items_in_default_order())
    right = Plan(
        items=[
            PlanItem(
                id="E1",
                type=PlanItemType.EPIC,
                title="Epic",
                goal="Different goal",
                requirements=["R1"],
                acceptance_criteria=["AC1"],
            )
        ]
    )

    assert hasher.compute_plan_id(left) != hasher.compute_plan_id(right)


def test_empty_and_missing_optional_containers_hash_the_same() -> None:
    hasher = PlanHasher()
    without_optional_containers = Plan(
        items=[
            PlanItem(
                id="E1",
                type=PlanItemType.EPIC,
                title="Epic",
                goal="Goal",
                requirements=["R1"],
                acceptance_criteria=["AC1"],
            )
        ]
    )
    with_empty_optional_containers = Plan(
        items=[
            PlanItem(
                id="E1",
                type=PlanItemType.EPIC,
                title="Epic",
                goal="Goal",
                requirements=["R1"],
                acceptance_criteria=["AC1"],
                scope=Scope(in_scope=[], out_scope=[]),
                verification=Verification(commands=[], ci_checks=[], evidence=[], manual_steps=[]),
            )
        ]
    )

    assert hasher.compute_plan_id(without_optional_containers) == hasher.compute_plan_id(with_empty_optional_containers)


def test_hash_format_is_12_hex_chars() -> None:
    plan = Plan(items=_plan_items_in_default_order())
    value = PlanHasher().compute_plan_id(plan)

    assert re.fullmatch(r"[0-9a-f]{12}", value) is not None
