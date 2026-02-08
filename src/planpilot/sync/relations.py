"""Relation roll-up logic for blocked-by propagation."""

from __future__ import annotations

from planpilot.models.plan import Task


def compute_story_blocked_by(
    tasks: list[Task],
) -> set[tuple[str, str]]:
    """Compute story-level blocked-by from task dependencies.

    When a task in story A depends on a task in story B (A != B),
    story A is blocked by story B.

    Args:
        tasks: List of all tasks in the plan.

    Returns:
        Set of (story_id, blocked_by_story_id) tuples.
    """
    task_story = {t.id: t.story_id for t in tasks}
    result: set[tuple[str, str]] = set()
    for task in tasks:
        for dep in task.depends_on:
            dep_story = task_story.get(dep)
            if dep_story and task.story_id != dep_story:
                result.add((task.story_id, dep_story))
    return result


def compute_epic_blocked_by(
    story_blocked_by: set[tuple[str, str]],
    story_epic_map: dict[str, str],
) -> set[tuple[str, str]]:
    """Compute epic-level blocked-by from story-level blocked-by.

    When a story in epic A is blocked by a story in epic B (A != B),
    epic A is blocked by epic B.

    Args:
        story_blocked_by: Set of (story_id, blocked_by_story_id).
        story_epic_map: Mapping of story_id to epic_id.

    Returns:
        Set of (epic_id, blocked_by_epic_id) tuples.
    """
    result: set[tuple[str, str]] = set()
    for story_id, blocked_by_story_id in story_blocked_by:
        epic_id = story_epic_map.get(story_id)
        blocked_by_epic_id = story_epic_map.get(blocked_by_story_id)
        if epic_id and blocked_by_epic_id and epic_id != blocked_by_epic_id:
            result.add((epic_id, blocked_by_epic_id))
    return result
