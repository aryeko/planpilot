"""Markdown renderer implementation."""

from __future__ import annotations

from planpilot_v2.contracts.plan import PlanItem, Scope, SpecRef
from planpilot_v2.contracts.renderer import BodyRenderer, RenderContext


def bullets(items: list[str]) -> str:
    return "\n".join(f"* {item}" for item in items)


def scope_block(scope: Scope) -> str:
    chunks: list[str] = []
    if scope.in_scope:
        chunks.append(f"In:\n\n{bullets(scope.in_scope)}")
    if scope.out_scope:
        chunks.append(f"Out:\n\n{bullets(scope.out_scope)}")
    return "\n\n".join(chunks)


def spec_ref_block(spec_ref: SpecRef | str) -> str:
    if isinstance(spec_ref, str):
        return f"* {spec_ref}"

    line = f"* [{spec_ref.url}]({spec_ref.url})"
    if spec_ref.section:
        line += f" ({spec_ref.section})"
    if spec_ref.quote:
        line += f' - "{spec_ref.quote}"'
    return line


class MarkdownRenderer(BodyRenderer):
    def render(self, item: PlanItem, context: RenderContext) -> str:
        metadata_block = "\n".join(
            [
                "PLANPILOT_META_V1",
                f"PLAN_ID:{context.plan_id}",
                f"ITEM_ID:{item.id}",
                "END_PLANPILOT_META",
            ]
        )
        sections: list[str] = [metadata_block]

        if item.goal:
            sections.append(f"## Goal\n\n{item.goal}")
        if item.motivation:
            sections.append(f"## Motivation\n\n{item.motivation}")
        if context.parent_ref:
            sections.append(f"## Parent\n\n* {context.parent_ref}")
        if item.scope:
            block = scope_block(item.scope)
            if block:
                sections.append(f"## Scope\n\n{block}")
        if item.requirements:
            sections.append(f"## Requirements\n\n{bullets(item.requirements)}")
        if item.acceptance_criteria:
            sections.append(f"## Acceptance Criteria\n\n{bullets(item.acceptance_criteria)}")
        if item.assumptions:
            sections.append(f"## Assumptions\n\n{bullets(item.assumptions)}")
        if item.risks:
            sections.append(f"## Risks\n\n{bullets(item.risks)}")
        if item.estimate and (item.estimate.tshirt is not None or item.estimate.hours is not None):
            estimate_parts: list[str] = []
            if item.estimate.tshirt is not None:
                estimate_parts.append(item.estimate.tshirt)
            if item.estimate.hours is not None:
                estimate_parts.append(f"({item.estimate.hours:g}h)")
            sections.append(f"## Estimate\n\n{' '.join(estimate_parts)}")
        if item.verification:
            verification_sections: list[str] = []
            if item.verification.commands:
                verification_sections.append(f"Commands:\n\n{bullets(item.verification.commands)}")
            if item.verification.ci_checks:
                verification_sections.append(f"CI checks:\n\n{bullets(item.verification.ci_checks)}")
            if item.verification.evidence:
                verification_sections.append(f"Evidence:\n\n{bullets(item.verification.evidence)}")
            if item.verification.manual_steps:
                verification_sections.append(f"Manual steps:\n\n{bullets(item.verification.manual_steps)}")
            if verification_sections:
                verification_block = "\n\n".join(verification_sections)
                sections.append(f"## Verification\n\n{verification_block}")
        if item.spec_ref:
            sections.append(f"## Spec Reference\n\n{spec_ref_block(item.spec_ref)}")
        if item.success_metrics:
            sections.append(f"## Success Metrics\n\n{bullets(item.success_metrics)}")
        if context.sub_items:
            ordered_sub_items = sorted(context.sub_items, key=lambda sub_item: (sub_item[0], sub_item[1]))
            checklist = "\n".join(f"* [ ] {key} {title}" for key, title in ordered_sub_items)
            sections.append(f"## Sub-items\n\n{checklist}")
        if context.dependencies:
            deps = [context.dependencies[dep_id] for dep_id in sorted(context.dependencies)]
            sections.append(f"## Dependencies\n\nBlocked by:\n\n{bullets(deps)}")

        return "\n\n".join(sections) + "\n"
