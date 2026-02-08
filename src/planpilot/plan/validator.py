"""Relational validation for a Plan (cross-entity integrity checks)."""

from __future__ import annotations

from planpilot.exceptions import PlanValidationError
from planpilot.models.plan import Plan


def validate_plan(plan: Plan) -> None:
    """Validate relational integrity of a pre-sliced, single-epic plan.

    This validator is intended for plans that have already been sliced by
    ``slice_epics_for_sync()`` into per-epic inputs.  It enforces exactly
    one epic and checks cross-entity references: epic↔story, story↔task,
    and task dependencies.

    Raises:
        PlanValidationError: Aggregated list of all validation errors found.
    """
    errors: list[str] = []

    if len(plan.epics) != 1:
        errors.append("plan must contain exactly one epic")

    epic_ids = {e.id for e in plan.epics}
    story_ids = {s.id for s in plan.stories}
    task_ids = {t.id for t in plan.tasks}

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
        extras = set(story_tasks.get(story.id, [])) - set(story.task_ids)
        if extras:
            errors.append(f"story {story.id} missing task_ids for {sorted(extras)}")
        if not story.task_ids and not story_tasks.get(story.id):
            errors.append(f"story {story.id} has no tasks")

    if plan.epics:
        epic = plan.epics[0]
        missing_stories = [sid for sid in epic.story_ids if sid not in story_ids]
        if missing_stories:
            errors.append(f"epic {epic.id} references unknown story_ids {missing_stories}")
        extras = set(story_ids) - set(epic.story_ids)
        if extras:
            errors.append(f"epic {epic.id} missing story_ids for {sorted(extras)}")

    if errors:
        raise PlanValidationError(errors)
