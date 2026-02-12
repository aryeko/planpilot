from planpilot.contracts.plan import Estimate, PlanItem, PlanItemType, Scope, SpecRef, Verification
from planpilot.contracts.renderer import RenderContext
from planpilot.renderers.markdown import MarkdownRenderer

SPEC_REFERENCE = (
    '## Spec Reference\n\n* [https://example.com/spec](https://example.com/spec) (2.1) - "Important detail"'
)


def test_render_minimal_item_includes_only_metadata_and_goal() -> None:
    renderer = MarkdownRenderer()
    item = PlanItem(id="T1", type=PlanItemType.TASK, title="Task one", goal="Ship v2 renderer")
    context = RenderContext(plan_id="plan-123")

    body = renderer.render(item, context)

    assert body.startswith(
        "PLANPILOT_META_V1\nPLAN_ID:plan-123\nITEM_ID:T1\nITEM_TYPE:TASK\nPARENT_ID:\nEND_PLANPILOT_META"
    )
    assert "## Goal\n\nShip v2 renderer" in body
    assert "## Motivation" not in body
    assert "## Parent" not in body
    assert "## Requirements" not in body
    assert "## Dependencies" not in body


def test_render_renders_all_populated_sections() -> None:
    renderer = MarkdownRenderer()
    item = PlanItem(
        id="S1",
        type=PlanItemType.STORY,
        title="Story one",
        goal="Deliver story body",
        motivation="Needed for rollout",
        requirements=["A", "B"],
        acceptance_criteria=["C"],
        success_metrics=["D"],
        assumptions=["E"],
        risks=["F"],
        estimate=Estimate(tshirt="M", hours=5),
        verification=Verification(
            commands=["pytest tests/renderers -q"],
            ci_checks=["lint"],
            evidence=["screenshot.png"],
            manual_steps=["open preview"],
        ),
        spec_ref=SpecRef(url="https://example.com/spec", section="2.1", quote="Important detail"),
        scope=Scope(in_scope=["renderer"], out_scope=["provider"]),
    )
    context = RenderContext(
        plan_id="plan-abc",
        parent_ref="#10",
        sub_items=[("#13", "Task c"), ("#12", "Task b")],
        dependencies={"D2": "#22", "D1": "#21"},
    )

    body = renderer.render(item, context)

    assert "## Motivation\n\nNeeded for rollout" in body
    assert "## Parent\n\n* #10" in body
    assert "## Scope\n\nIn:\n\n* renderer\n\nOut:\n\n* provider" in body
    assert "## Requirements\n\n* A\n* B" in body
    assert "## Acceptance Criteria\n\n* C" in body
    assert "## Assumptions\n\n* E" in body
    assert "## Risks\n\n* F" in body
    assert "## Estimate\n\nM (5h)" in body
    assert "## Verification" in body
    assert "Commands:\n\n* pytest tests/renderers -q" in body
    assert "CI checks:\n\n* lint" in body
    assert "Evidence:\n\n* screenshot.png" in body
    assert "Manual steps:\n\n* open preview" in body
    assert SPEC_REFERENCE in body
    assert "## Success Metrics\n\n* D" in body
    assert "## Sub-items" in body
    assert "## Dependencies\n\nBlocked by:" in body


def test_render_orders_sub_items_and_dependencies_deterministically() -> None:
    renderer = MarkdownRenderer()
    item = PlanItem(id="E1", type=PlanItemType.EPIC, title="Epic one")
    context = RenderContext(
        plan_id="plan-xyz",
        sub_items=[("#20", "Zulu"), ("#10", "Alpha"), ("#10", "Beta")],
        dependencies={"B": "#200", "A": "#100"},
    )

    body = renderer.render(item, context)

    sub_alpha = body.index("* [ ] #10 Alpha")
    sub_beta = body.index("* [ ] #10 Beta")
    sub_zulu = body.index("* [ ] #20 Zulu")
    dep_100 = body.index("* #100")
    dep_200 = body.index("* #200")

    assert sub_alpha < sub_beta < sub_zulu
    assert dep_100 < dep_200


def test_render_omits_scope_when_empty() -> None:
    renderer = MarkdownRenderer()
    item = PlanItem(id="T2", type=PlanItemType.TASK, title="Task two", scope=Scope())
    context = RenderContext(plan_id="plan-999")

    body = renderer.render(item, context)

    assert "## Scope" not in body


def test_render_formats_string_spec_reference() -> None:
    renderer = MarkdownRenderer()
    item = PlanItem.model_construct(id="T3", type=PlanItemType.TASK, title="Task", goal="Goal", spec_ref="SPEC-9")
    context = RenderContext(plan_id="plan-100")

    body = renderer.render(item, context)

    assert "## Spec Reference\n\n* SPEC-9" in body


def test_render_handles_partial_estimate_and_verification_sections() -> None:
    renderer = MarkdownRenderer()
    item = PlanItem(
        id="T4",
        type=PlanItemType.TASK,
        title="Task four",
        estimate=Estimate(hours=2),
        verification=Verification(evidence=["trace-id"]),
    )
    context = RenderContext(plan_id="plan-101")

    body = renderer.render(item, context)

    assert "## Estimate\n\n(2h)" in body
    assert "## Verification" in body
    assert "Evidence:\n\n* trace-id" in body
    assert "Commands:" not in body
    assert "CI checks:" not in body
    assert "Manual steps:" not in body
