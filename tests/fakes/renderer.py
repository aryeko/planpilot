"""Deterministic renderer fake for v2 tests."""

from __future__ import annotations

from planpilot.contracts.plan import PlanItem
from planpilot.contracts.renderer import BodyRenderer, RenderContext


class FakeRenderer(BodyRenderer):
    def render(self, item: PlanItem, context: RenderContext) -> str:
        lines = [
            "PLANPILOT_META_V1",
            f"PLAN_ID:{context.plan_id}",
            f"ITEM_ID:{item.id}",
            "END_PLANPILOT_META",
            "",
            f"# {item.title}",
        ]
        if context.parent_ref:
            lines.append(f"Parent: {context.parent_ref}")
        for key, title in context.sub_items:
            lines.append(f"Sub: {key} {title}")
        for _, ref in sorted(context.dependencies.items()):
            lines.append(f"Dep: {ref}")
        return "\n".join(lines)
