from planpilot_v2.contracts.plan import PlanItem, PlanItemType
from planpilot_v2.contracts.renderer import RenderContext
from tests.v2.fakes.renderer import FakeRenderer


def test_fake_renderer_includes_metadata_and_context_lines() -> None:
    renderer = FakeRenderer()
    item = PlanItem(id="T1", type=PlanItemType.TASK, title="Task one")
    context = RenderContext(
        plan_id="plan-123",
        parent_ref="#1",
        sub_items=[("#2", "Story two")],
        dependencies={"A": "#10"},
    )

    body = renderer.render(item, context)

    assert "PLANPILOT_META_V1" in body
    assert "PLAN_ID:plan-123" in body
    assert "ITEM_ID:T1" in body
    assert "END_PLANPILOT_META" in body
    assert "Parent: #1" in body
    assert "Sub: #2 Story two" in body
    assert "Dep: #10" in body
