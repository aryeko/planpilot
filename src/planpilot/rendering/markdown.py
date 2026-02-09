"""Markdown body renderer for GitHub-compatible issue bodies."""

from __future__ import annotations

from planpilot.models.plan import Epic, Story, Task
from planpilot.rendering.components import bullets, scope_block, spec_ref_block


class MarkdownRenderer:
    """Renders issue bodies as GitHub-flavoured Markdown."""

    def render_epic(self, epic: Epic, plan_id: str, stories_list: str | None = None) -> str:
        """Render the body for an epic issue.

        Args:
            epic: The epic model.
            plan_id: Deterministic plan hash for the marker comment.
            stories_list: Pre-rendered stories checklist, or None.

        Returns:
            Rendered body string.
        """
        stories_section = stories_list if stories_list is not None else "* (populated after stories are created)"
        return (
            f"<!-- PLAN_ID: {plan_id} -->\n\n"
            f"<!-- EPIC_ID: {epic.id} -->\n\n"
            f"## Goal\n\n{epic.goal}\n\n"
            f"## Scope\n\n{scope_block(epic.scope)}\n\n"
            f"## Success metrics\n\n{bullets(epic.success_metrics)}\n\n"
            f"## Risks\n\n{bullets(epic.risks)}\n\n"
            f"## Assumptions\n\n{bullets(epic.assumptions)}\n\n"
            f"## Spec reference\n\n{spec_ref_block(epic.spec_ref)}\n\n"
            f"## Stories\n\n{stories_section}\n"
        )

    def render_story(self, story: Story, plan_id: str, epic_ref: str, tasks_list: str | None = None) -> str:
        """Render the body for a story issue.

        Args:
            story: The story model.
            plan_id: Deterministic plan hash.
            epic_ref: Reference to the parent epic (e.g. "#42").
            tasks_list: Pre-rendered tasks checklist, or None.

        Returns:
            Rendered body string.
        """
        tasks_block = tasks_list if tasks_list is not None else "* (populated after tasks are created)"
        return (
            f"<!-- PLAN_ID: {plan_id} -->\n\n"
            f"<!-- STORY_ID: {story.id} -->\n\n"
            f"## Epic\n\n* {epic_ref}\n\n"
            f"## Goal\n\n{story.goal}\n\n"
            f"## Scope\n\n{scope_block(story.scope)}\n\n"
            f"## Success metrics\n\n{bullets(story.success_metrics)}\n\n"
            f"## Risks\n\n{bullets(story.risks)}\n\n"
            f"## Assumptions\n\n{bullets(story.assumptions)}\n\n"
            f"## Spec reference\n\n{spec_ref_block(story.spec_ref)}\n\n"
            f"## Tasks\n\n{tasks_block}\n"
        )

    def render_task(self, task: Task, plan_id: str, story_ref: str, deps_block: str) -> str:
        """Render the body for a task issue.

        Args:
            task: The task model.
            plan_id: Deterministic plan hash.
            story_ref: Reference to the parent story (e.g. "#43").
            deps_block: Pre-rendered dependencies block.

        Returns:
            Rendered body string.
        """
        v = task.verification
        manual_block = ""
        if v.manual_steps:
            manual_block = f"\n\nManual steps:\n\n{bullets(v.manual_steps)}"
        return (
            f"<!-- PLAN_ID: {plan_id} -->\n\n"
            f"<!-- TASK_ID: {task.id} -->\n\n"
            f"## Story\n\n* {story_ref}\n\n"
            f"## Motivation\n\n{task.motivation}\n\n"
            f"## Scope\n\n{scope_block(task.scope)}\n\n"
            f"## Requirements\n\n{bullets(task.requirements)}\n\n"
            f"## Acceptance criteria\n\n{bullets(task.acceptance_criteria)}\n\n"
            f"## Verification\n\n"
            f"Commands:\n\n{bullets(v.commands)}\n\n"
            f"CI checks:\n\n{bullets(v.ci_checks)}\n\n"
            f"Evidence:\n\n{bullets(v.evidence)}{manual_block}\n\n"
            f"## Artifacts\n\n{bullets(task.artifacts)}\n\n"
            f"## Spec reference\n\n{spec_ref_block(task.spec_ref)}\n\n"
            f"## Dependencies\n\n{deps_block}\n"
        )

    def render_checklist(self, items: list[tuple[str, str]]) -> str:
        """Render a checklist of (item_key, title) pairs.

        Args:
            items: List of (key, title) tuples where key is a string
                   reference (e.g. "#123" for GitHub, "PROJ-456" for Jira).

        Returns:
            Rendered checklist string.
        """
        if not items:
            return "* (none)"
        return "\n".join(f"* [ ] {key} {title}" for key, title in items)

    def render_deps_block(self, deps: dict[str, str]) -> str:
        """Render a dependency block from {task_id: issue_ref} mapping.

        Args:
            deps: Mapping of task ID to issue reference (e.g. "#10").

        Returns:
            Rendered dependency block.
        """
        if not deps:
            return "Blocked by:\n\n* (none)"
        items = "\n".join(f"* {ref}" for ref in deps.values())
        return f"Blocked by:\n\n{items}"
