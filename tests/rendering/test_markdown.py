"""Tests for MarkdownRenderer class."""

from __future__ import annotations

from planpilot.models.plan import Epic, Scope, Story, Task, Verification
from planpilot.rendering.markdown import MarkdownRenderer


def test_render_epic_basic():
    """Test render_epic() produces correct structure with markers."""
    epic = Epic(
        id="epic-1",
        title="Test Epic",
        goal="Test goal",
        spec_ref="spec.md",
        story_ids=[],
    )
    renderer = MarkdownRenderer()
    result = renderer.render_epic(epic, plan_id="plan-123")

    assert "<!-- PLAN_ID: plan-123 -->" in result
    assert "<!-- EPIC_ID: epic-1 -->" in result
    assert "## Goal" in result
    assert "Test goal" in result
    assert "## Scope" in result
    assert "## Success metrics" in result
    assert "## Risks" in result
    assert "## Assumptions" in result
    assert "## Spec reference" in result
    assert "## Stories" in result
    assert result.endswith("\n")


def test_render_epic_with_stories_list():
    """Test render_epic() with provided stories_list."""
    epic = Epic(
        id="epic-1",
        title="Test Epic",
        goal="Test goal",
        spec_ref="spec.md",
        story_ids=[],
    )
    renderer = MarkdownRenderer()
    stories_list = "* [ ] #1 Story 1\n* [ ] #2 Story 2"
    result = renderer.render_epic(epic, plan_id="plan-123", stories_list=stories_list)

    assert stories_list in result
    assert "* (populated after stories are created)" not in result


def test_render_epic_without_stories_list():
    """Test render_epic() without stories_list uses placeholder."""
    epic = Epic(
        id="epic-1",
        title="Test Epic",
        goal="Test goal",
        spec_ref="spec.md",
        story_ids=[],
    )
    renderer = MarkdownRenderer()
    result = renderer.render_epic(epic, plan_id="plan-123")

    assert "* (populated after stories are created)" in result


def test_render_epic_with_scope():
    """Test render_epic() renders scope correctly."""
    epic = Epic(
        id="epic-1",
        title="Test Epic",
        goal="Test goal",
        spec_ref="spec.md",
        story_ids=[],
        scope=Scope(in_scope=["item1"], out_scope=["item2"]),
    )
    renderer = MarkdownRenderer()
    result = renderer.render_epic(epic, plan_id="plan-123")

    assert "In:\n\n* item1" in result
    assert "Out:\n\n* item2" in result


def test_render_story_basic():
    """Test render_story() produces correct structure with markers."""
    story = Story(
        id="story-1",
        epic_id="epic-1",
        title="Test Story",
        goal="Test goal",
        spec_ref="spec.md",
        task_ids=[],
    )
    renderer = MarkdownRenderer()
    result = renderer.render_story(story, plan_id="plan-123", epic_ref="#42")

    assert "<!-- PLAN_ID: plan-123 -->" in result
    assert "<!-- STORY_ID: story-1 -->" in result
    assert "## Epic" in result
    assert "* #42" in result
    assert "## Goal" in result
    assert "Test goal" in result
    assert "## Scope" in result
    assert "## Success metrics" in result
    assert "## Risks" in result
    assert "## Assumptions" in result
    assert "## Spec reference" in result
    assert "## Tasks" in result
    assert result.endswith("\n")


def test_render_story_with_tasks_list():
    """Test render_story() with provided tasks_list."""
    story = Story(
        id="story-1",
        epic_id="epic-1",
        title="Test Story",
        goal="Test goal",
        spec_ref="spec.md",
        task_ids=[],
    )
    renderer = MarkdownRenderer()
    tasks_list = "* [ ] #10 Task 1\n* [ ] #11 Task 2"
    result = renderer.render_story(story, plan_id="plan-123", epic_ref="#42", tasks_list=tasks_list)

    assert tasks_list in result
    assert "* (populated after tasks are created)" not in result


def test_render_story_without_tasks_list():
    """Test render_story() without tasks_list uses placeholder."""
    story = Story(
        id="story-1",
        epic_id="epic-1",
        title="Test Story",
        goal="Test goal",
        spec_ref="spec.md",
        task_ids=[],
    )
    renderer = MarkdownRenderer()
    result = renderer.render_story(story, plan_id="plan-123", epic_ref="#42")

    assert "* (populated after tasks are created)" in result


def test_render_task_basic():
    """Test render_task() produces correct structure with markers."""
    task = Task(
        id="task-1",
        story_id="story-1",
        title="Test Task",
        motivation="Test motivation",
        spec_ref="spec.md",
        requirements=[],
        acceptance_criteria=[],
        artifacts=[],
        depends_on=[],
    )
    renderer = MarkdownRenderer()
    deps_block = "Blocked by:\n\n* (none)"
    result = renderer.render_task(task, plan_id="plan-123", story_ref="#43", deps_block=deps_block)

    assert "<!-- PLAN_ID: plan-123 -->" in result
    assert "<!-- TASK_ID: task-1 -->" in result
    assert "## Story" in result
    assert "* #43" in result
    assert "## Motivation" in result
    assert "Test motivation" in result
    assert "## Scope" in result
    assert "## Requirements" in result
    assert "## Acceptance criteria" in result
    assert "## Verification" in result
    assert "Commands:" in result
    assert "CI checks:" in result
    assert "Evidence:" in result
    assert "## Artifacts" in result
    assert "## Spec reference" in result
    assert "## Dependencies" in result
    assert deps_block in result
    assert result.endswith("\n")


def test_render_task_with_manual_steps():
    """Test render_task() includes manual steps section when present."""
    task = Task(
        id="task-1",
        story_id="story-1",
        title="Test Task",
        motivation="Test motivation",
        spec_ref="spec.md",
        requirements=[],
        acceptance_criteria=[],
        artifacts=[],
        depends_on=[],
        verification=Verification(manual_steps=["Step 1", "Step 2"]),
    )
    renderer = MarkdownRenderer()
    deps_block = "Blocked by:\n\n* (none)"
    result = renderer.render_task(task, plan_id="plan-123", story_ref="#43", deps_block=deps_block)

    assert "Manual steps:" in result
    assert "* Step 1" in result
    assert "* Step 2" in result


def test_render_task_without_manual_steps():
    """Test render_task() omits manual steps section when empty."""
    task = Task(
        id="task-1",
        story_id="story-1",
        title="Test Task",
        motivation="Test motivation",
        spec_ref="spec.md",
        requirements=[],
        acceptance_criteria=[],
        artifacts=[],
        depends_on=[],
    )
    renderer = MarkdownRenderer()
    deps_block = "Blocked by:\n\n* (none)"
    result = renderer.render_task(task, plan_id="plan-123", story_ref="#43", deps_block=deps_block)

    assert "Manual steps:" not in result


def test_render_checklist_empty():
    """Test render_checklist() with empty list."""
    renderer = MarkdownRenderer()
    assert renderer.render_checklist([]) == "* (none)"


def test_render_checklist_single_item():
    """Test render_checklist() with single item."""
    renderer = MarkdownRenderer()
    result = renderer.render_checklist([(1, "Task 1")])
    assert result == "* [ ] #1 Task 1"


def test_render_checklist_multiple_items():
    """Test render_checklist() with multiple items."""
    renderer = MarkdownRenderer()
    result = renderer.render_checklist([(1, "Task 1"), (2, "Task 2"), (3, "Task 3")])
    expected = "* [ ] #1 Task 1\n* [ ] #2 Task 2\n* [ ] #3 Task 3"
    assert result == expected


def test_render_deps_block_empty():
    """Test render_deps_block() with empty dict."""
    renderer = MarkdownRenderer()
    result = renderer.render_deps_block({})
    assert result == "Blocked by:\n\n* (none)"


def test_render_deps_block_single():
    """Test render_deps_block() with single dependency."""
    renderer = MarkdownRenderer()
    result = renderer.render_deps_block({"task-1": "#10"})
    assert result == "Blocked by:\n\n* #10"


def test_render_deps_block_multiple():
    """Test render_deps_block() with multiple dependencies."""
    renderer = MarkdownRenderer()
    result = renderer.render_deps_block({"task-1": "#10", "task-2": "#11", "task-3": "#12"})
    expected = "Blocked by:\n\n* #10\n* #11\n* #12"
    assert result == expected


def test_render_epic_body_ends_with_newline():
    """Test render_epic() body ends with exactly one newline."""
    epic = Epic(
        id="epic-1",
        title="Test Epic",
        goal="Test goal",
        spec_ref="spec.md",
        story_ids=[],
    )
    renderer = MarkdownRenderer()
    result = renderer.render_epic(epic, plan_id="plan-123")

    assert result.endswith("\n")
    assert not result.endswith("\n\n")


def test_render_story_body_ends_with_newline():
    """Test render_story() body ends with exactly one newline."""
    story = Story(
        id="story-1",
        epic_id="epic-1",
        title="Test Story",
        goal="Test goal",
        spec_ref="spec.md",
        task_ids=[],
    )
    renderer = MarkdownRenderer()
    result = renderer.render_story(story, plan_id="plan-123", epic_ref="#42")

    assert result.endswith("\n")
    assert not result.endswith("\n\n")


def test_render_task_body_ends_with_newline():
    """Test render_task() body ends with exactly one newline."""
    task = Task(
        id="task-1",
        story_id="story-1",
        title="Test Task",
        motivation="Test motivation",
        spec_ref="spec.md",
        requirements=[],
        acceptance_criteria=[],
        artifacts=[],
        depends_on=[],
    )
    renderer = MarkdownRenderer()
    deps_block = "Blocked by:\n\n* (none)"
    result = renderer.render_task(task, plan_id="plan-123", story_ref="#43", deps_block=deps_block)

    assert result.endswith("\n")
    assert not result.endswith("\n\n")


def test_render_epic_body_stripped():
    """Test render_epic() body is properly stripped (no leading/trailing whitespace)."""
    epic = Epic(
        id="epic-1",
        title="Test Epic",
        goal="Test goal",
        spec_ref="spec.md",
        story_ids=[],
    )
    renderer = MarkdownRenderer()
    result = renderer.render_epic(epic, plan_id="plan-123")

    # Should start with comment marker, not whitespace
    assert result.startswith("<!--")


def test_render_story_body_stripped():
    """Test render_story() body is properly stripped."""
    story = Story(
        id="story-1",
        epic_id="epic-1",
        title="Test Story",
        goal="Test goal",
        spec_ref="spec.md",
        task_ids=[],
    )
    renderer = MarkdownRenderer()
    result = renderer.render_story(story, plan_id="plan-123", epic_ref="#42")

    assert result.startswith("<!--")


def test_render_task_body_stripped():
    """Test render_task() body is properly stripped."""
    task = Task(
        id="task-1",
        story_id="story-1",
        title="Test Task",
        motivation="Test motivation",
        spec_ref="spec.md",
        requirements=[],
        acceptance_criteria=[],
        artifacts=[],
        depends_on=[],
    )
    renderer = MarkdownRenderer()
    deps_block = "Blocked by:\n\n* (none)"
    result = renderer.render_task(task, plan_id="plan-123", story_ref="#43", deps_block=deps_block)

    assert result.startswith("<!--")
