"""Tests for project models: FieldConfig, ProjectContext, RepoContext, IssueRef, etc."""

from __future__ import annotations

from planpilot.models.enums import EntityType
from planpilot.models.project import (
    CreateIssueInput,
    ExistingIssue,
    FieldConfig,
    FieldValue,
    IssueRef,
    IssueTypeMap,
    ProjectContext,
    RelationMap,
    RepoContext,
    ResolvedField,
)


class TestFieldConfig:
    """Tests for FieldConfig model."""

    def test_field_config_defaults_are_correct(self) -> None:
        """FieldConfig defaults are correct."""
        config = FieldConfig()
        assert config.status == "Backlog"
        assert config.priority == "P1"
        assert config.iteration == "active"
        assert config.size_field == "Size"
        assert config.size_from_tshirt is True

    def test_field_config_with_custom_values(self) -> None:
        """FieldConfig can be created with custom values."""
        config = FieldConfig(
            status="In Progress",
            priority="P0",
            iteration="sprint-1",
            size_field="Story Points",
            size_from_tshirt=False,
        )
        assert config.status == "In Progress"
        assert config.priority == "P0"
        assert config.iteration == "sprint-1"
        assert config.size_field == "Story Points"
        assert config.size_from_tshirt is False


class TestFieldValue:
    """Tests for FieldValue model."""

    def test_field_value_with_single_select_option_id(self) -> None:
        """FieldValue with single_select_option_id."""
        value = FieldValue(single_select_option_id="option-123")
        assert value.single_select_option_id == "option-123"
        assert value.iteration_id is None
        assert value.text is None
        assert value.number is None

    def test_field_value_with_iteration_id(self) -> None:
        """FieldValue with iteration_id."""
        value = FieldValue(iteration_id="iter-456")
        assert value.single_select_option_id is None
        assert value.iteration_id == "iter-456"
        assert value.text is None
        assert value.number is None

    def test_field_value_with_text(self) -> None:
        """FieldValue with text."""
        value = FieldValue(text="Some text")
        assert value.single_select_option_id is None
        assert value.iteration_id is None
        assert value.text == "Some text"
        assert value.number is None

    def test_field_value_with_number(self) -> None:
        """FieldValue with number."""
        value = FieldValue(number=42.5)
        assert value.single_select_option_id is None
        assert value.iteration_id is None
        assert value.text is None
        assert value.number == 42.5


class TestResolvedField:
    """Tests for ResolvedField model."""

    def test_resolved_field_creation(self) -> None:
        """ResolvedField creation."""
        field_value = FieldValue(single_select_option_id="option-123")
        resolved = ResolvedField(field_id="field-789", value=field_value)
        assert resolved.field_id == "field-789"
        assert resolved.value.single_select_option_id == "option-123"


class TestProjectContext:
    """Tests for ProjectContext model."""

    def test_project_context_with_item_map(self) -> None:
        """ProjectContext with item_map."""
        context = ProjectContext(
            project_id="proj-123",
            item_map={"issue-1": "item-1", "issue-2": "item-2"},
        )
        assert context.project_id == "proj-123"
        assert context.item_map == {"issue-1": "item-1", "issue-2": "item-2"}
        assert context.status_field is None
        assert context.priority_field is None
        assert context.iteration_field is None
        assert context.size_field_id is None
        assert context.size_options == []

    def test_project_context_with_all_fields(self) -> None:
        """ProjectContext with all fields populated."""
        status_value = FieldValue(single_select_option_id="status-1")
        priority_value = FieldValue(single_select_option_id="priority-1")
        iteration_value = FieldValue(iteration_id="iter-1")
        context = ProjectContext(
            project_id="proj-123",
            status_field=ResolvedField(field_id="status-field", value=status_value),
            priority_field=ResolvedField(field_id="priority-field", value=priority_value),
            iteration_field=ResolvedField(field_id="iteration-field", value=iteration_value),
            size_field_id="size-field",
            size_options=[{"id": "s1", "name": "Small"}],
            item_map={"issue-1": "item-1"},
        )
        assert context.project_id == "proj-123"
        assert context.status_field is not None
        assert context.priority_field is not None
        assert context.iteration_field is not None
        assert context.size_field_id == "size-field"
        assert len(context.size_options) == 1


class TestRepoContext:
    """Tests for RepoContext model."""

    def test_repo_context_with_issue_type_ids(self) -> None:
        """RepoContext with issue_type_ids."""
        issue_type_ids: IssueTypeMap = {"Epic": "epic-id", "Story": "story-id", "Task": "task-id"}
        context = RepoContext(
            repo_id="repo-123",
            label_id="label-456",
            issue_type_ids=issue_type_ids,
        )
        assert context.repo_id == "repo-123"
        assert context.label_id == "label-456"
        assert context.issue_type_ids == issue_type_ids

    def test_repo_context_defaults(self) -> None:
        """RepoContext defaults."""
        context = RepoContext()
        assert context.repo_id is None
        assert context.label_id is None
        assert context.issue_type_ids == {}


class TestIssueRef:
    """Tests for IssueRef model."""

    def test_issue_ref_creation(self) -> None:
        """IssueRef creation."""
        issue_ref = IssueRef(id="issue-123", number=42, url="https://github.com/owner/repo/issues/42")
        assert issue_ref.id == "issue-123"
        assert issue_ref.number == 42
        assert issue_ref.url == "https://github.com/owner/repo/issues/42"


class TestExistingIssue:
    """Tests for ExistingIssue model."""

    def test_existing_issue_creation(self) -> None:
        """ExistingIssue creation."""
        issue = ExistingIssue(id="issue-123", number=42, body="Issue body")
        assert issue.id == "issue-123"
        assert issue.number == 42
        assert issue.body == "Issue body"

    def test_existing_issue_default_body(self) -> None:
        """ExistingIssue defaults body to empty string."""
        issue = ExistingIssue(id="issue-123", number=42)
        assert issue.body == ""


class TestCreateIssueInput:
    """Tests for CreateIssueInput model."""

    def test_create_issue_input_without_label_ids(self) -> None:
        """CreateIssueInput with and without label_ids."""
        input_data = CreateIssueInput(
            repo_id="repo-123",
            title="Test Issue",
            body="Issue body",
        )
        assert input_data.repo_id == "repo-123"
        assert input_data.title == "Test Issue"
        assert input_data.body == "Issue body"
        assert input_data.label_ids == []

    def test_create_issue_input_with_label_ids(self) -> None:
        """CreateIssueInput with label_ids."""
        input_data = CreateIssueInput(
            repo_id="repo-123",
            title="Test Issue",
            body="Issue body",
            label_ids=["label-1", "label-2"],
        )
        assert input_data.label_ids == ["label-1", "label-2"]


class TestRelationMap:
    """Tests for RelationMap model."""

    def test_relation_map_with_parents_and_blocked_by(self) -> None:
        """RelationMap with parents and blocked_by."""
        relation_map = RelationMap(
            parents={"issue-1": "parent-1", "issue-2": None},
            blocked_by={"issue-1": {"blocker-1", "blocker-2"}},
        )
        assert relation_map.parents == {"issue-1": "parent-1", "issue-2": None}
        assert relation_map.blocked_by == {"issue-1": {"blocker-1", "blocker-2"}}

    def test_relation_map_defaults(self) -> None:
        """RelationMap defaults."""
        relation_map = RelationMap()
        assert relation_map.parents == {}
        assert relation_map.blocked_by == {}


class TestEntityType:
    """Tests for EntityType enum."""

    def test_entity_type_enum_values(self) -> None:
        """EntityType enum values."""
        assert EntityType.EPIC == "epic"
        assert EntityType.STORY == "story"
        assert EntityType.TASK == "task"

    def test_entity_type_string_comparison(self) -> None:
        """EntityType can be compared to strings."""
        assert EntityType.EPIC == "epic"
        assert EntityType.STORY == "story"
        assert EntityType.TASK == "task"
