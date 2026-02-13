from planpilot.core.contracts.plan import Plan, PlanItem, PlanItemType


def test_plan_item_type_enum_values() -> None:
    assert PlanItemType.EPIC.value == "EPIC"
    assert PlanItemType.STORY.value == "STORY"
    assert PlanItemType.TASK.value == "TASK"


def test_plan_item_mutable_defaults_are_not_shared() -> None:
    first = PlanItem(id="E1", type=PlanItemType.EPIC, title="Epic one")
    second = PlanItem(id="E2", type=PlanItemType.EPIC, title="Epic two")

    first.depends_on.append("X")

    assert second.depends_on == []


def test_plan_holds_plan_items() -> None:
    plan = Plan(items=[PlanItem(id="E1", type=PlanItemType.EPIC, title="Epic")])

    assert len(plan.items) == 1
    assert plan.items[0].id == "E1"
