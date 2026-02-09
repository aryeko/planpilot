"""Protocol defining how issue bodies are rendered.

Providers that use a different markup language (e.g. Jira wiki) can supply
their own renderer implementing this protocol.
"""

from __future__ import annotations

from typing import Protocol

from planpilot.models.plan import Epic, Story, Task


class BodyRenderer(Protocol):
    """Structural-typing protocol for issue body renderers."""

    def render_epic(
        self,
        epic: Epic,
        plan_id: str,
        stories_list: str | None = None,
    ) -> str:
        """Render the body for an epic issue.

        Args:
            epic: The epic model.
            plan_id: Deterministic plan hash for the marker comment.
            stories_list: Pre-rendered stories checklist, or *None*.

        Returns:
            Rendered body string.
        """
        ...

    def render_story(
        self,
        story: Story,
        plan_id: str,
        epic_ref: str,
        tasks_list: str | None = None,
    ) -> str:
        """Render the body for a story issue.

        Args:
            story: The story model.
            plan_id: Deterministic plan hash.
            epic_ref: Reference to the parent epic (e.g. ``"#42"``).
            tasks_list: Pre-rendered tasks checklist, or *None*.

        Returns:
            Rendered body string.
        """
        ...

    def render_task(
        self,
        task: Task,
        plan_id: str,
        story_ref: str,
        deps_block: str,
    ) -> str:
        """Render the body for a task issue.

        Args:
            task: The task model.
            plan_id: Deterministic plan hash.
            story_ref: Reference to the parent story (e.g. ``"#43"``).
            deps_block: Pre-rendered dependencies block.

        Returns:
            Rendered body string.
        """
        ...

    def render_checklist(self, items: list[tuple[str, str]]) -> str:
        """Render a checklist of ``(item_key, title)`` pairs.

        Args:
            items: List of ``(key, title)`` tuples. key is a string
                   reference (e.g. ``"#123"`` for GitHub, ``"PROJ-456"`` for Jira).

        Returns:
            Rendered checklist string.
        """
        ...

    def render_deps_block(self, deps: dict[str, str]) -> str:
        """Render a dependency block from ``{task_id: issue_ref}`` mapping.

        Args:
            deps: Mapping of task ID to issue reference (e.g. ``"#10"``).

        Returns:
            Rendered dependency block.
        """
        ...
