"""Tests for plan models: Epic, Story, Task, Plan, Scope, SpecRef, Estimate, Verification."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from planpilot.models.plan import (
    Epic,
    Estimate,
    Plan,
    Scope,
    SpecRef,
    Story,
    Task,
    Verification,
)


class TestEpic:
    """Tests for Epic model."""

    def test_epic_with_all_required_fields_succeeds(self) -> None:
        """Epic created with all required fields succeeds."""
        epic = Epic(
            id="E-1",
            title="Test Epic",
            goal="Test goal",
            spec_ref="spec.md",
            story_ids=["S-1"],
        )
        assert epic.id == "E-1"
        assert epic.title == "Test Epic"
        assert epic.goal == "Test goal"
        assert epic.spec_ref == "spec.md"
        assert epic.story_ids == ["S-1"]

    def test_epic_missing_required_field_raises_validation_error(self) -> None:
        """Epic missing required field (e.g. goal) raises ValidationError."""
        with pytest.raises(ValidationError):
            Epic(
                id="E-1",
                title="Test Epic",
                # Missing goal
                spec_ref="spec.md",
                story_ids=["S-1"],
            )

    def test_epic_defaults(self) -> None:
        """Epic defaults work (scope, success_metrics, risks, assumptions all default to empty)."""
        epic = Epic(
            id="E-1",
            title="Test Epic",
            goal="Test goal",
            spec_ref="spec.md",
            story_ids=["S-1"],
        )
        assert epic.scope == Scope()
        assert epic.success_metrics == []
        assert epic.risks == []
        assert epic.assumptions == []

    def test_epic_with_spec_ref_as_string(self) -> None:
        """SpecRef as string works on Epic."""
        epic = Epic(
            id="E-1",
            title="Test Epic",
            goal="Test goal",
            spec_ref="spec.md",
            story_ids=["S-1"],
        )
        assert epic.spec_ref == "spec.md"

    def test_epic_with_spec_ref_as_model(self) -> None:
        """SpecRef as dict/model works."""
        spec_ref = SpecRef(path="spec.md", anchor="section1", section="Overview", quote="text")
        epic = Epic(
            id="E-1",
            title="Test Epic",
            goal="Test goal",
            spec_ref=spec_ref,
            story_ids=["S-1"],
        )
        assert isinstance(epic.spec_ref, SpecRef)
        assert epic.spec_ref.path == "spec.md"
        assert epic.spec_ref.anchor == "section1"
        assert epic.spec_ref.section == "Overview"
        assert epic.spec_ref.quote == "text"


class TestStory:
    """Tests for Story model."""

    def test_story_with_all_required_fields_succeeds(self) -> None:
        """Story created with all required fields succeeds."""
        story = Story(
            id="S-1",
            epic_id="E-1",
            title="Test Story",
            goal="Story goal",
            spec_ref="spec.md",
            task_ids=["T-1"],
        )
        assert story.id == "S-1"
        assert story.epic_id == "E-1"
        assert story.title == "Test Story"
        assert story.goal == "Story goal"
        assert story.spec_ref == "spec.md"
        assert story.task_ids == ["T-1"]

    def test_story_missing_required_field_raises_validation_error(self) -> None:
        """Story missing required field raises ValidationError."""
        with pytest.raises(ValidationError):
            Story(
                id="S-1",
                epic_id="E-1",
                title="Test Story",
                # Missing goal
                spec_ref="spec.md",
                task_ids=["T-1"],
            )

    def test_story_defaults(self) -> None:
        """Story defaults work (scope, success_metrics, risks, assumptions all default to empty)."""
        story = Story(
            id="S-1",
            epic_id="E-1",
            title="Test Story",
            goal="Story goal",
            spec_ref="spec.md",
            task_ids=["T-1"],
        )
        assert story.scope == Scope()
        assert story.success_metrics == []
        assert story.risks == []
        assert story.assumptions == []

    def test_story_with_spec_ref_as_string(self) -> None:
        """SpecRef as string works on Story."""
        story = Story(
            id="S-1",
            epic_id="E-1",
            title="Test Story",
            goal="Story goal",
            spec_ref="spec.md",
            task_ids=["T-1"],
        )
        assert story.spec_ref == "spec.md"

    def test_story_with_spec_ref_as_model(self) -> None:
        """SpecRef as dict/model works."""
        spec_ref = SpecRef(path="spec.md", anchor="section2")
        story = Story(
            id="S-1",
            epic_id="E-1",
            title="Test Story",
            goal="Story goal",
            spec_ref=spec_ref,
            task_ids=["T-1"],
        )
        assert isinstance(story.spec_ref, SpecRef)
        assert story.spec_ref.path == "spec.md"


class TestTask:
    """Tests for Task model."""

    def test_task_with_all_required_fields_succeeds(self) -> None:
        """Task created with all required fields succeeds."""
        task = Task(
            id="T-1",
            story_id="S-1",
            title="Test Task",
            motivation="Task motivation",
            spec_ref="spec.md",
            requirements=["req1"],
            acceptance_criteria=["ac1"],
            verification=Verification(),
            artifacts=["artifact1"],
            depends_on=[],
        )
        assert task.id == "T-1"
        assert task.story_id == "S-1"
        assert task.title == "Test Task"
        assert task.motivation == "Task motivation"
        assert task.spec_ref == "spec.md"
        assert task.requirements == ["req1"]
        assert task.acceptance_criteria == ["ac1"]
        assert task.artifacts == ["artifact1"]
        assert task.depends_on == []

    def test_task_missing_required_field_raises_validation_error(self) -> None:
        """Task missing required field raises ValidationError."""
        with pytest.raises(ValidationError):
            Task(
                id="T-1",
                story_id="S-1",
                title="Test Task",
                # Missing motivation
                spec_ref="spec.md",
                requirements=["req1"],
                acceptance_criteria=["ac1"],
                verification=Verification(),
                artifacts=["artifact1"],
                depends_on=[],
            )

    def test_task_defaults(self) -> None:
        """Task defaults work (scope, estimate, verification all default appropriately)."""
        task = Task(
            id="T-1",
            story_id="S-1",
            title="Test Task",
            motivation="Task motivation",
            spec_ref="spec.md",
            requirements=["req1"],
            acceptance_criteria=["ac1"],
            verification=Verification(),
            artifacts=["artifact1"],
            depends_on=[],
        )
        assert task.scope == Scope()
        assert task.estimate == Estimate()
        assert task.verification == Verification()

    def test_task_with_spec_ref_as_string(self) -> None:
        """SpecRef as string works on Task."""
        task = Task(
            id="T-1",
            story_id="S-1",
            title="Test Task",
            motivation="Task motivation",
            spec_ref="spec.md",
            requirements=["req1"],
            acceptance_criteria=["ac1"],
            verification=Verification(),
            artifacts=["artifact1"],
            depends_on=[],
        )
        assert task.spec_ref == "spec.md"

    def test_task_with_spec_ref_as_model(self) -> None:
        """SpecRef as dict/model works."""
        spec_ref = SpecRef(path="spec.md", section="Implementation")
        task = Task(
            id="T-1",
            story_id="S-1",
            title="Test Task",
            motivation="Task motivation",
            spec_ref=spec_ref,
            requirements=["req1"],
            acceptance_criteria=["ac1"],
            verification=Verification(),
            artifacts=["artifact1"],
            depends_on=[],
        )
        assert isinstance(task.spec_ref, SpecRef)
        assert task.spec_ref.path == "spec.md"


class TestPlan:
    """Tests for Plan model."""

    def test_plan_created_from_valid_components_succeeds(
        self, sample_epic: Epic, sample_story: Story, sample_task: Task
    ) -> None:
        """Plan created from valid components succeeds."""
        plan = Plan(epics=[sample_epic], stories=[sample_story], tasks=[sample_task])
        assert len(plan.epics) == 1
        assert len(plan.stories) == 1
        assert len(plan.tasks) == 1
        assert plan.epics[0].id == "E-1"
        assert plan.stories[0].id == "S-1"
        assert plan.tasks[0].id == "T-1"

    def test_plan_with_empty_lists(self) -> None:
        """Plan can be created with empty lists."""
        plan = Plan(epics=[], stories=[], tasks=[])
        assert plan.epics == []
        assert plan.stories == []
        assert plan.tasks == []


class TestScope:
    """Tests for Scope model."""

    def test_scope_with_alias_in_out_works(self) -> None:
        """Scope with alias 'in'/'out' works."""
        scope = Scope(in_scope=["item1", "item2"], out_scope=["item3"])
        assert scope.in_scope == ["item1", "item2"]
        assert scope.out_scope == ["item3"]

    def test_scope_defaults(self) -> None:
        """Scope defaults to empty lists."""
        scope = Scope()
        assert scope.in_scope == []
        assert scope.out_scope == []

    def test_scope_populate_by_name(self) -> None:
        """Scope can be populated by alias 'in'/'out'."""
        scope_dict = {"in": ["item1"], "out": ["item2"]}
        scope = Scope(**scope_dict)
        assert scope.in_scope == ["item1"]
        assert scope.out_scope == ["item2"]


class TestSpecRef:
    """Tests for SpecRef model."""

    def test_spec_ref_with_all_fields(self) -> None:
        """SpecRef can be created with all fields."""
        spec_ref = SpecRef(path="spec.md", anchor="section1", section="Overview", quote="text")
        assert spec_ref.path == "spec.md"
        assert spec_ref.anchor == "section1"
        assert spec_ref.section == "Overview"
        assert spec_ref.quote == "text"

    def test_spec_ref_defaults(self) -> None:
        """SpecRef defaults anchor, section, quote to empty strings."""
        spec_ref = SpecRef(path="spec.md")
        assert spec_ref.path == "spec.md"
        assert spec_ref.anchor == ""
        assert spec_ref.section == ""
        assert spec_ref.quote == ""


class TestEstimate:
    """Tests for Estimate model."""

    def test_estimate_defaults(self) -> None:
        """Estimate defaults (empty tshirt, None hours)."""
        estimate = Estimate()
        assert estimate.tshirt == ""
        assert estimate.hours is None

    def test_estimate_with_values(self) -> None:
        """Estimate can be created with tshirt and hours."""
        estimate = Estimate(tshirt="M", hours=8.0)
        assert estimate.tshirt == "M"
        assert estimate.hours == 8.0


class TestVerification:
    """Tests for Verification model."""

    def test_verification_defaults(self) -> None:
        """Verification defaults (empty lists)."""
        verification = Verification()
        assert verification.commands == []
        assert verification.ci_checks == []
        assert verification.evidence == []
        assert verification.manual_steps == []

    def test_verification_with_values(self) -> None:
        """Verification can be created with values."""
        verification = Verification(
            commands=["npm test"],
            ci_checks=["lint", "typecheck"],
            evidence=["screenshot.png"],
            manual_steps=["Check UI"],
        )
        assert verification.commands == ["npm test"]
        assert verification.ci_checks == ["lint", "typecheck"]
        assert verification.evidence == ["screenshot.png"]
        assert verification.manual_steps == ["Check UI"]
