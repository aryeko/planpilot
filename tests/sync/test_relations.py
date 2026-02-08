"""Tests for relation roll-up logic."""

from __future__ import annotations

from planpilot.models.plan import Task
from planpilot.sync.relations import compute_epic_blocked_by, compute_story_blocked_by


class TestComputeStoryBlockedBy:
    """Tests for compute_story_blocked_by function."""

    def test_no_dependencies_returns_empty_set(self):
        """No dependencies should return empty set."""
        tasks = [
            Task(
                id="T-1",
                story_id="S-1",
                title="Task 1",
                motivation="Motivation",
                spec_ref="spec.md",
                requirements=[],
                acceptance_criteria=[],
                artifacts=[],
                depends_on=[],
            ),
            Task(
                id="T-2",
                story_id="S-2",
                title="Task 2",
                motivation="Motivation",
                spec_ref="spec.md",
                requirements=[],
                acceptance_criteria=[],
                artifacts=[],
                depends_on=[],
            ),
        ]
        result = compute_story_blocked_by(tasks)
        assert result == set()

    def test_same_story_dependencies_no_blocked_by(self):
        """Tasks within the same story don't produce story-level blocked-by."""
        tasks = [
            Task(
                id="T-1",
                story_id="S-1",
                title="Task 1",
                motivation="Motivation",
                spec_ref="spec.md",
                requirements=[],
                acceptance_criteria=[],
                artifacts=[],
                depends_on=[],
            ),
            Task(
                id="T-2",
                story_id="S-1",
                title="Task 2",
                motivation="Motivation",
                spec_ref="spec.md",
                requirements=[],
                acceptance_criteria=[],
                artifacts=[],
                depends_on=["T-1"],
            ),
        ]
        result = compute_story_blocked_by(tasks)
        assert result == set()

    def test_cross_story_dependencies_create_blocked_by(self):
        """Tasks depending on tasks in different stories produce story-level blocked-by."""
        tasks = [
            Task(
                id="T-1",
                story_id="S-1",
                title="Task 1",
                motivation="Motivation",
                spec_ref="spec.md",
                requirements=[],
                acceptance_criteria=[],
                artifacts=[],
                depends_on=[],
            ),
            Task(
                id="T-2",
                story_id="S-2",
                title="Task 2",
                motivation="Motivation",
                spec_ref="spec.md",
                requirements=[],
                acceptance_criteria=[],
                artifacts=[],
                depends_on=["T-1"],
            ),
        ]
        result = compute_story_blocked_by(tasks)
        assert result == {("S-2", "S-1")}

    def test_multiple_cross_story_dependencies(self):
        """Multiple cross-story dependencies are all captured."""
        tasks = [
            Task(
                id="T-1",
                story_id="S-1",
                title="Task 1",
                motivation="Motivation",
                spec_ref="spec.md",
                requirements=[],
                acceptance_criteria=[],
                artifacts=[],
                depends_on=[],
            ),
            Task(
                id="T-2",
                story_id="S-2",
                title="Task 2",
                motivation="Motivation",
                spec_ref="spec.md",
                requirements=[],
                acceptance_criteria=[],
                artifacts=[],
                depends_on=["T-1"],
            ),
            Task(
                id="T-3",
                story_id="S-3",
                title="Task 3",
                motivation="Motivation",
                spec_ref="spec.md",
                requirements=[],
                acceptance_criteria=[],
                artifacts=[],
                depends_on=["T-1", "T-2"],
            ),
        ]
        result = compute_story_blocked_by(tasks)
        assert result == {("S-2", "S-1"), ("S-3", "S-1"), ("S-3", "S-2")}

    def test_missing_dependency_id_ignored(self):
        """Dependencies to non-existent tasks are ignored."""
        tasks = [
            Task(
                id="T-1",
                story_id="S-1",
                title="Task 1",
                motivation="Motivation",
                spec_ref="spec.md",
                requirements=[],
                acceptance_criteria=[],
                artifacts=[],
                depends_on=["T-MISSING"],
            ),
        ]
        result = compute_story_blocked_by(tasks)
        assert result == set()


class TestComputeEpicBlockedBy:
    """Tests for compute_epic_blocked_by function."""

    def test_no_story_blocked_by_returns_empty_set(self):
        """No story-level blocked-by returns empty set."""
        story_blocked_by = set()
        story_epic_map = {"S-1": "E-1", "S-2": "E-2"}
        result = compute_epic_blocked_by(story_blocked_by, story_epic_map)
        assert result == set()

    def test_same_epic_stories_no_blocked_by(self):
        """Stories within the same epic don't produce epic-level blocked-by."""
        story_blocked_by = {("S-1", "S-2")}
        story_epic_map = {"S-1": "E-1", "S-2": "E-1"}
        result = compute_epic_blocked_by(story_blocked_by, story_epic_map)
        assert result == set()

    def test_cross_epic_stories_create_blocked_by(self):
        """Cross-epic story dependencies produce epic-level blocked-by."""
        story_blocked_by = {("S-1", "S-2")}
        story_epic_map = {"S-1": "E-1", "S-2": "E-2"}
        result = compute_epic_blocked_by(story_blocked_by, story_epic_map)
        assert result == {("E-1", "E-2")}

    def test_multiple_cross_epic_dependencies(self):
        """Multiple cross-epic dependencies are all captured."""
        story_blocked_by = {("S-1", "S-2"), ("S-1", "S-3"), ("S-2", "S-4")}
        story_epic_map = {
            "S-1": "E-1",
            "S-2": "E-1",
            "S-3": "E-2",
            "S-4": "E-3",
        }
        result = compute_epic_blocked_by(story_blocked_by, story_epic_map)
        assert result == {("E-1", "E-2"), ("E-1", "E-3")}

    def test_missing_story_in_map_ignored(self):
        """Stories not in the map are ignored."""
        story_blocked_by = {("S-1", "S-MISSING"), ("S-MISSING", "S-2")}
        story_epic_map = {"S-1": "E-1", "S-2": "E-2"}
        result = compute_epic_blocked_by(story_blocked_by, story_epic_map)
        assert result == set()
