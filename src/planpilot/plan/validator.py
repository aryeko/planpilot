"""Relational validation for a Plan (cross-entity integrity checks)."""

from __future__ import annotations

from planpilot.exceptions import PlanValidationError
from planpilot.models.plan import Plan


def validate_plan(plan: Plan) -> None:
    """Validate relational integrity of a plan.

    Supports single-epic and multi-epic plans. Validates cross-entity
    references: epic↔story, story↔task, and task dependencies.

    Raises:
        PlanValidationError: Aggregated list of all validation errors found.
    """
    errors: list[str] = []

    if len(plan.epics) < 1:
        errors.append("plan must contain at least one epic")

    epic_ids = {e.id for e in plan.epics}
    story_ids = {s.id for s in plan.stories}
    task_ids = {t.id for t in plan.tasks}
    task_by_id = {t.id: t for t in plan.tasks}

    # Track which tasks belong to which story
    story_tasks: dict[str, list[str]] = {sid: [] for sid in story_ids}

    for task in plan.tasks:
        if task.story_id not in story_ids:
            errors.append(f"task {task.id} story_id '{task.story_id}' not found in stories")
            continue
        story_tasks[task.story_id].append(task.id)
        for dep in task.depends_on:
            if dep not in task_ids:
                errors.append(f"task {task.id} depends_on '{dep}' not found in tasks")

    for story in plan.stories:
        if story.epic_id not in epic_ids:
            errors.append(f"story {story.id} epic_id '{story.epic_id}' not found in epics")
        missing = [tid for tid in story.task_ids if tid not in task_ids]
        if missing:
            errors.append(f"story {story.id} references unknown task_ids {missing}")
        # Verify referenced tasks actually belong to this story
        for tid in story.task_ids:
            if tid in task_by_id and task_by_id[tid].story_id != story.id:
                errors.append(
                    f"story {story.id} references task {tid} but task.story_id is '{task_by_id[tid].story_id}'"
                )
        extras = set(story_tasks.get(story.id, [])) - set(story.task_ids)
        if extras:
            errors.append(f"story {story.id} missing task_ids for {sorted(extras)}")
        if not story.task_ids and not story_tasks.get(story.id):
            errors.append(f"story {story.id} has no tasks")

    for epic in plan.epics:
        missing_stories = [sid for sid in epic.story_ids if sid not in story_ids]
        if missing_stories:
            errors.append(f"epic {epic.id} references unknown story_ids {missing_stories}")

        epic_story_ids = {story.id for story in plan.stories if story.epic_id == epic.id}
        extras = epic_story_ids - set(epic.story_ids)
        if extras:
            errors.append(f"epic {epic.id} missing story_ids for {sorted(extras)}")

    if errors:
        raise PlanValidationError(errors)
