"""Tests for plan validator."""

from __future__ import annotations

import pytest

from planpilot.exceptions import PlanValidationError
from planpilot.models.plan import Epic, Estimate, Plan, Scope, Story, Task, Verification
from planpilot.plan.validator import validate_plan


def create_minimal_plan() -> Plan:
    """Create a minimal valid plan for testing."""
    epic = Epic(
        id="epic1",
        title="Epic",
        goal="Goal",
        spec_ref="spec.md",
        story_ids=["story1"],
        scope=Scope(),
        success_metrics=[],
        risks=[],
        assumptions=[],
    )
    story = Story(
        id="story1",
        epic_id="epic1",
        title="Story",
        goal="Goal",
        spec_ref="spec.md",
        task_ids=["task1"],
        scope=Scope(),
        success_metrics=[],
        risks=[],
        assumptions=[],
    )
    task = Task(
        id="task1",
        story_id="story1",
        title="Task",
        motivation="Motivation",
        spec_ref="spec.md",
        requirements=[],
        acceptance_criteria=[],
        verification=Verification(),
        artifacts=[],
        depends_on=[],
        estimate=Estimate(),
        scope=Scope(),
    )
    return Plan(epics=[epic], stories=[story], tasks=[task])


def test_validate_plan_exactly_one_epic():
    """Test that plan must contain exactly one epic."""
    plan = create_minimal_plan()
    plan.epics = []  # Zero epics

    with pytest.raises(PlanValidationError) as exc_info:
        validate_plan(plan)

    assert "exactly one epic" in str(exc_info.value).lower()

    plan.epics = [
        Epic(id="e1", title="E1", goal="G", spec_ref="s", story_ids=[]),
        Epic(id="e2", title="E2", goal="G", spec_ref="s", story_ids=[]),
    ]

    with pytest.raises(PlanValidationError) as exc_info:
        validate_plan(plan)

    assert "exactly one epic" in str(exc_info.value).lower()


def test_validate_plan_task_story_id_reference():
    """Test that task.story_id must reference an existing story."""
    plan = create_minimal_plan()
    plan.tasks[0].story_id = "nonexistent"

    with pytest.raises(PlanValidationError) as exc_info:
        validate_plan(plan)

    assert "story_id 'nonexistent' not found" in str(exc_info.value)


def test_validate_plan_task_depends_on_reference():
    """Test that task.depends_on entries must reference existing tasks."""
    plan = create_minimal_plan()
    plan.tasks[0].depends_on = ["nonexistent"]

    with pytest.raises(PlanValidationError) as exc_info:
        validate_plan(plan)

    assert "depends_on 'nonexistent' not found" in str(exc_info.value)


def test_validate_plan_story_epic_id_reference():
    """Test that story.epic_id must reference an existing epic."""
    plan = create_minimal_plan()
    plan.stories[0].epic_id = "nonexistent"

    with pytest.raises(PlanValidationError) as exc_info:
        validate_plan(plan)

    assert "epic_id 'nonexistent' not found" in str(exc_info.value)


def test_validate_plan_story_task_ids_reference():
    """Test that story.task_ids must all exist in tasks."""
    plan = create_minimal_plan()
    plan.stories[0].task_ids = ["nonexistent"]

    with pytest.raises(PlanValidationError) as exc_info:
        validate_plan(plan)

    assert "references unknown task_ids" in str(exc_info.value)


def test_validate_plan_tasks_must_be_listed_in_story():
    """Test that tasks with a story_id must be listed in that story's task_ids."""
    plan = create_minimal_plan()
    # Add a task that's not listed in the story's task_ids
    extra_task = Task(
        id="task2",
        story_id="story1",
        title="Task2",
        motivation="Motivation",
        spec_ref="spec.md",
        requirements=[],
        acceptance_criteria=[],
        verification=Verification(),
        artifacts=[],
        depends_on=[],
        estimate=Estimate(),
        scope=Scope(),
    )
    plan.tasks.append(extra_task)

    with pytest.raises(PlanValidationError) as exc_info:
        validate_plan(plan)

    assert "missing task_ids for" in str(exc_info.value)
    assert "task2" in str(exc_info.value)


def test_validate_plan_story_zero_tasks():
    """Test that story with zero tasks raises error."""
    plan = create_minimal_plan()
    # Remove the task and clear task_ids to create a story with truly no tasks
    plan.tasks = []
    plan.stories[0].task_ids = []
    plan.epics[0].story_ids = ["story1"]  # Keep story in epic

    with pytest.raises(PlanValidationError) as exc_info:
        validate_plan(plan)

    assert "has no tasks" in str(exc_info.value)


def test_validate_plan_epic_story_ids_reference():
    """Test that epic.story_ids must all exist in stories."""
    plan = create_minimal_plan()
    plan.epics[0].story_ids = ["nonexistent"]

    with pytest.raises(PlanValidationError) as exc_info:
        validate_plan(plan)

    assert "references unknown story_ids" in str(exc_info.value)


def test_validate_plan_stories_must_be_listed_in_epic():
    """Test that stories not listed in any epic's story_ids raises error."""
    plan = create_minimal_plan()
    # Add a story that's not listed in the epic's story_ids
    extra_story = Story(
        id="story2",
        epic_id="epic1",
        title="Story2",
        goal="Goal",
        spec_ref="spec.md",
        task_ids=[],
        scope=Scope(),
        success_metrics=[],
        risks=[],
        assumptions=[],
    )
    plan.stories.append(extra_story)

    with pytest.raises(PlanValidationError) as exc_info:
        validate_plan(plan)

    assert "missing story_ids for" in str(exc_info.value)
    assert "story2" in str(exc_info.value)


def test_validate_plan_valid_plan_passes():
    """Test that a valid plan passes without error."""
    plan = create_minimal_plan()

    # Should not raise any exception
    validate_plan(plan)


def test_validate_plan_multiple_errors():
    """Test that validator collects multiple errors."""
    plan = create_minimal_plan()
    plan.tasks[0].story_id = "nonexistent"
    plan.stories[0].epic_id = "nonexistent"
    plan.epics[0].story_ids = ["nonexistent"]

    with pytest.raises(PlanValidationError) as exc_info:
        validate_plan(plan)

    error_str = str(exc_info.value)
    assert "story_id 'nonexistent' not found" in error_str
    assert "epic_id 'nonexistent' not found" in error_str
    assert "references unknown story_ids" in error_str
