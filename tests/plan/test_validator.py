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


def create_valid_multi_epic_plan() -> Plan:
    """Create a valid plan with two epics for native multi-epic support tests."""
    epic1 = Epic(id="epic1", title="Epic 1", goal="Goal", spec_ref="spec.md", story_ids=["story1"], scope=Scope())
    epic2 = Epic(id="epic2", title="Epic 2", goal="Goal", spec_ref="spec.md", story_ids=["story2"], scope=Scope())

    story1 = Story(
        id="story1",
        epic_id="epic1",
        title="Story 1",
        goal="Goal",
        spec_ref="spec.md",
        task_ids=["task1"],
        scope=Scope(),
    )
    story2 = Story(
        id="story2",
        epic_id="epic2",
        title="Story 2",
        goal="Goal",
        spec_ref="spec.md",
        task_ids=["task2"],
        scope=Scope(),
    )

    task1 = Task(
        id="task1",
        story_id="story1",
        title="Task 1",
        motivation="Motivation",
        spec_ref="spec.md",
        requirements=[],
        acceptance_criteria=[],
        verification=Verification(),
        artifacts=[],
        depends_on=["task2"],
        estimate=Estimate(),
        scope=Scope(),
    )
    task2 = Task(
        id="task2",
        story_id="story2",
        title="Task 2",
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

    return Plan(epics=[epic1, epic2], stories=[story1, story2], tasks=[task1, task2])


def test_validate_plan_requires_at_least_one_epic():
    """Test that plan must contain at least one epic."""
    plan = create_minimal_plan()
    plan.epics = []  # Zero epics

    with pytest.raises(PlanValidationError) as exc_info:
        validate_plan(plan)

    assert "at least one epic" in str(exc_info.value).lower()


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


def test_validate_plan_task_story_id_cross_reference():
    """Test that story.task_ids can't reference tasks owned by a different story."""
    plan = create_minimal_plan()
    # Add a second story with a second task
    story2 = Story(
        id="story2",
        epic_id="epic1",
        title="Story2",
        goal="Goal",
        spec_ref="spec.md",
        task_ids=["task1"],  # Incorrectly claims task1 (owned by story1)
        scope=Scope(),
        success_metrics=[],
        risks=[],
        assumptions=[],
    )
    task2 = Task(
        id="task2",
        story_id="story2",
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
    plan.stories.append(story2)
    plan.tasks.append(task2)
    plan.epics[0].story_ids = ["story1", "story2"]

    with pytest.raises(PlanValidationError) as exc_info:
        validate_plan(plan)

    error_str = str(exc_info.value)
    assert "story story2 references task task1" in error_str
    assert "task.story_id is 'story1'" in error_str


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


def test_validate_plan_multi_epic_valid_plan_passes() -> None:
    """Native validator should accept valid plans with multiple epics."""
    plan = create_valid_multi_epic_plan()

    validate_plan(plan)


def test_validate_plan_multi_epic_cross_references_are_validated() -> None:
    """Native validator should report cross-epic mismatches without single-epic errors."""
    plan = create_valid_multi_epic_plan()
    plan.stories[1].epic_id = "missing-epic"
    plan.tasks[1].story_id = "missing-story"

    with pytest.raises(PlanValidationError) as exc_info:
        validate_plan(plan)

    message = str(exc_info.value)
    assert "story story2 epic_id 'missing-epic' not found in epics" in message
    assert "task task2 story_id 'missing-story' not found in stories" in message
    assert "exactly one epic" not in message


def test_validate_plan_rejects_epic_story_ids_owned_by_other_epic() -> None:
    """An epic cannot list a story owned by another epic."""
    plan = create_valid_multi_epic_plan()
    plan.epics[0].story_ids = ["story1", "story2"]

    with pytest.raises(PlanValidationError) as exc_info:
        validate_plan(plan)

    assert "references story_ids owned by a different epic" in str(exc_info.value)


def test_validate_plan_rejects_duplicate_entity_ids() -> None:
    """Duplicate epic/story/task IDs are invalid."""
    plan = create_minimal_plan()
    plan.epics.append(Epic(id="epic1", title="Epic dup", goal="Goal", spec_ref="spec.md", story_ids=["story1"]))
    plan.stories.append(
        Story(id="story1", epic_id="epic1", title="Story dup", goal="Goal", spec_ref="spec.md", task_ids=["task1"])
    )
    plan.tasks.append(
        Task(
            id="task1",
            story_id="story1",
            title="Task dup",
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
    )

    with pytest.raises(PlanValidationError) as exc_info:
        validate_plan(plan)

    error_str = str(exc_info.value)
    assert "duplicate epic ids" in error_str
    assert "duplicate story ids" in error_str
    assert "duplicate task ids" in error_str
