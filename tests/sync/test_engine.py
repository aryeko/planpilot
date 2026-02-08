"""Tests for SyncEngine."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from planpilot.config import SyncConfig
from planpilot.models.plan import Epic, Plan, Story, Task
from planpilot.models.project import (
    CreateIssueInput,
    ExistingIssue,
    FieldValue,
    IssueRef,
    ProjectContext,
    RelationMap,
    RepoContext,
    ResolvedField,
)
from planpilot.models.sync import SyncMap, SyncResult
from planpilot.plan import compute_plan_id, load_plan
from planpilot.providers.base import Provider
from planpilot.rendering.base import BodyRenderer
from planpilot.sync.engine import SyncEngine


@pytest.fixture
def mock_provider() -> AsyncMock:
    """Mock Provider instance."""
    provider = AsyncMock(spec=Provider)
    provider.check_auth = AsyncMock()
    provider.get_repo_context = AsyncMock()
    provider.get_project_context = AsyncMock()
    provider.search_issues = AsyncMock(return_value=[])
    provider.create_issue = AsyncMock()
    provider.update_issue = AsyncMock()
    provider.set_issue_type = AsyncMock()
    provider.add_to_project = AsyncMock()
    provider.set_project_field = AsyncMock()
    provider.get_issue_relations = AsyncMock()
    provider.add_sub_issue = AsyncMock()
    provider.add_blocked_by = AsyncMock()
    return provider


@pytest.fixture
def mock_renderer() -> MagicMock:
    """Mock BodyRenderer instance."""
    renderer = MagicMock(spec=BodyRenderer)
    renderer.render_epic = MagicMock(return_value="epic body")
    renderer.render_story = MagicMock(return_value="story body")
    renderer.render_task = MagicMock(return_value="task body")
    renderer.render_checklist = MagicMock(return_value="checklist")
    renderer.render_deps_block = MagicMock(return_value="deps block")
    return renderer


@pytest.fixture
def repo_context() -> RepoContext:
    """Sample RepoContext."""
    return RepoContext(
        repo_id="repo-123",
        label_id="label-456",
        issue_type_ids={"Epic": "epic-type", "Story": "story-type", "Task": "task-type"},
    )


@pytest.fixture
def project_context() -> ProjectContext:
    """Sample ProjectContext."""
    return ProjectContext(
        project_id="project-789",
        status_field=ResolvedField(field_id="status-field", value=FieldValue(single_select_option_id="backlog")),
        priority_field=ResolvedField(field_id="priority-field", value=FieldValue(single_select_option_id="p1")),
        iteration_field=ResolvedField(field_id="iteration-field", value=FieldValue(iteration_id="active")),
        size_field_id="size-field",
        size_options=[{"id": "s", "name": "S"}, {"id": "m", "name": "M"}],
    )


@pytest.fixture
def sample_plan_with_deps(tmp_path: Path) -> tuple[Plan, Path, Path, Path]:
    """Create a plan with cross-story dependencies."""
    epic = Epic(
        id="E-1",
        title="Epic 1",
        goal="Goal",
        spec_ref="spec.md",
        story_ids=["S-1", "S-2"],
    )
    story1 = Story(
        id="S-1",
        epic_id="E-1",
        title="Story 1",
        goal="Goal",
        spec_ref="spec.md",
        task_ids=["T-1"],
    )
    story2 = Story(
        id="S-2",
        epic_id="E-1",
        title="Story 2",
        goal="Goal",
        spec_ref="spec.md",
        task_ids=["T-2"],
    )
    task1 = Task(
        id="T-1",
        story_id="S-1",
        title="Task 1",
        motivation="Motivation",
        spec_ref="spec.md",
        requirements=[],
        acceptance_criteria=[],
        artifacts=[],
        depends_on=[],
    )
    task2 = Task(
        id="T-2",
        story_id="S-2",
        title="Task 2",
        motivation="Motivation",
        spec_ref="spec.md",
        requirements=[],
        acceptance_criteria=[],
        artifacts=[],
        depends_on=["T-1"],  # Cross-story dependency
    )
    plan = Plan(epics=[epic], stories=[story1, story2], tasks=[task1, task2])

    epics_path = tmp_path / "epics.json"
    stories_path = tmp_path / "stories.json"
    tasks_path = tmp_path / "tasks.json"
    epics_path.write_text(json.dumps([epic.model_dump(mode="json", by_alias=True)]), encoding="utf-8")
    stories_path.write_text(
        json.dumps([story1.model_dump(mode="json", by_alias=True), story2.model_dump(mode="json", by_alias=True)]),
        encoding="utf-8",
    )
    tasks_path.write_text(
        json.dumps([task1.model_dump(mode="json", by_alias=True), task2.model_dump(mode="json", by_alias=True)]),
        encoding="utf-8",
    )

    return plan, epics_path, stories_path, tasks_path


@pytest.mark.asyncio
async def test_sync_calls_check_auth(mock_provider, mock_renderer, plan_json_files, sample_config):
    """Sync engine calls provider.check_auth()."""
    epics_path, stories_path, tasks_path = plan_json_files
    config = SyncConfig(
        repo="owner/repo",
        project_url="https://github.com/orgs/org/projects/1",
        epics_path=epics_path,
        stories_path=stories_path,
        tasks_path=tasks_path,
        sync_path=sample_config.sync_path,
    )
    mock_provider.get_repo_context.return_value = RepoContext(repo_id="repo-123")
    mock_provider.get_project_context.return_value = None
    mock_provider.create_issue.return_value = IssueRef(
        id="issue-123", number=42, url="https://github.com/owner/repo/issues/42"
    )
    mock_provider.get_issue_relations.return_value = RelationMap(parents={}, blocked_by={})

    engine = SyncEngine(mock_provider, mock_renderer, config)
    await engine.sync()

    mock_provider.check_auth.assert_called_once()


@pytest.mark.asyncio
async def test_sync_fails_fast_on_missing_repo_id(mock_provider, mock_renderer, plan_json_files, sample_config):
    """Sync engine raises SyncError when repo context has no repo_id."""
    from planpilot.exceptions import SyncError

    epics_path, stories_path, tasks_path = plan_json_files
    config = SyncConfig(
        repo="owner/repo",
        project_url="https://github.com/orgs/org/projects/1",
        epics_path=epics_path,
        stories_path=stories_path,
        tasks_path=tasks_path,
        sync_path=sample_config.sync_path,
    )
    mock_provider.get_repo_context.return_value = RepoContext(repo_id=None)
    mock_provider.get_project_context.return_value = None

    engine = SyncEngine(mock_provider, mock_renderer, config)
    with pytest.raises(SyncError, match="missing repo_id"):
        await engine.sync()


@pytest.mark.asyncio
async def test_sync_loads_and_validates_plan(mock_provider, mock_renderer, plan_json_files, sample_config):
    """Sync engine loads and validates the plan."""
    epics_path, stories_path, tasks_path = plan_json_files
    config = SyncConfig(
        repo="owner/repo",
        project_url="https://github.com/orgs/org/projects/1",
        epics_path=epics_path,
        stories_path=stories_path,
        tasks_path=tasks_path,
        sync_path=sample_config.sync_path,
    )
    mock_provider.get_repo_context.return_value = RepoContext(repo_id="repo-123")
    mock_provider.get_project_context.return_value = None
    mock_provider.create_issue.return_value = IssueRef(
        id="issue-123", number=42, url="https://github.com/owner/repo/issues/42"
    )
    mock_provider.get_issue_relations.return_value = RelationMap(parents={}, blocked_by={})

    engine = SyncEngine(mock_provider, mock_renderer, config)
    result = await engine.sync()

    assert result.sync_map.plan_id  # Plan ID computed
    assert result.sync_map.repo == "owner/repo"


@pytest.mark.asyncio
async def test_sync_creates_epic_issue(
    mock_provider, mock_renderer, plan_json_files, sample_config, repo_context, project_context
):
    """Sync engine creates epic issue with proper setup."""
    epics_path, stories_path, tasks_path = plan_json_files
    config = SyncConfig(
        repo="owner/repo",
        project_url="https://github.com/orgs/org/projects/1",
        epics_path=epics_path,
        stories_path=stories_path,
        tasks_path=tasks_path,
        sync_path=sample_config.sync_path,
    )
    mock_provider.get_repo_context.return_value = repo_context
    mock_provider.get_project_context.return_value = project_context
    epic_ref = IssueRef(id="epic-123", number=42, url="https://github.com/owner/repo/issues/42")
    story_ref = IssueRef(id="story-456", number=43, url="https://github.com/owner/repo/issues/43")
    task_ref = IssueRef(id="task-789", number=44, url="https://github.com/owner/repo/issues/44")
    mock_provider.create_issue.side_effect = [epic_ref, story_ref, task_ref]
    mock_provider.add_to_project.return_value = "item-456"
    mock_provider.get_issue_relations.return_value = RelationMap(
        parents={"story-456": None, "task-789": None}, blocked_by={}
    )

    engine = SyncEngine(mock_provider, mock_renderer, config)
    await engine.sync()

    assert mock_provider.create_issue.call_count == 3  # epic, story, task
    call_args = mock_provider.create_issue.call_args_list[0][0][0]
    assert isinstance(call_args, CreateIssueInput)
    assert call_args.repo_id == "repo-123"
    mock_provider.set_issue_type.assert_any_call("epic-123", "epic-type")
    mock_provider.add_to_project.assert_called()


@pytest.mark.asyncio
async def test_sync_creates_story_issue(
    mock_provider, mock_renderer, plan_json_files, sample_config, repo_context, project_context
):
    """Sync engine creates story issue with epic reference."""
    epics_path, stories_path, tasks_path = plan_json_files
    config = SyncConfig(
        repo="owner/repo",
        project_url="https://github.com/orgs/org/projects/1",
        epics_path=epics_path,
        stories_path=stories_path,
        tasks_path=tasks_path,
        sync_path=sample_config.sync_path,
    )
    mock_provider.get_repo_context.return_value = repo_context
    mock_provider.get_project_context.return_value = project_context
    epic_ref = IssueRef(id="epic-123", number=10, url="https://github.com/owner/repo/issues/10")
    story_ref = IssueRef(id="story-456", number=11, url="https://github.com/owner/repo/issues/11")
    task_ref = IssueRef(id="task-789", number=12, url="https://github.com/owner/repo/issues/12")
    mock_provider.create_issue.side_effect = [epic_ref, story_ref, task_ref]
    mock_provider.add_to_project.return_value = "item-789"
    mock_provider.get_issue_relations.return_value = RelationMap(parents={}, blocked_by={})

    engine = SyncEngine(mock_provider, mock_renderer, config)
    await engine.sync()

    assert mock_provider.create_issue.call_count == 3  # epic, story, task
    mock_renderer.render_story.assert_called()
    # Verify epic_ref was passed containing the epic issue number
    call_args = mock_renderer.render_story.call_args
    positional_args = call_args[0]
    assert any("#10" in str(arg) for arg in positional_args)


@pytest.mark.asyncio
async def test_sync_creates_task_issue(
    mock_provider, mock_renderer, plan_json_files, sample_config, repo_context, project_context
):
    """Sync engine creates task issue with story reference."""
    epics_path, stories_path, tasks_path = plan_json_files
    config = SyncConfig(
        repo="owner/repo",
        project_url="https://github.com/orgs/org/projects/1",
        epics_path=epics_path,
        stories_path=stories_path,
        tasks_path=tasks_path,
        sync_path=sample_config.sync_path,
    )
    mock_provider.get_repo_context.return_value = repo_context
    mock_provider.get_project_context.return_value = project_context
    epic_ref = IssueRef(id="epic-123", number=10, url="https://github.com/owner/repo/issues/10")
    story_ref = IssueRef(id="story-456", number=11, url="https://github.com/owner/repo/issues/11")
    task_ref = IssueRef(id="task-789", number=12, url="https://github.com/owner/repo/issues/12")
    mock_provider.create_issue.side_effect = [epic_ref, story_ref, task_ref]
    mock_provider.add_to_project.return_value = "item-999"
    mock_provider.get_issue_relations.return_value = RelationMap(parents={}, blocked_by={})

    engine = SyncEngine(mock_provider, mock_renderer, config)
    await engine.sync()

    assert mock_provider.create_issue.call_count == 3
    mock_renderer.render_task.assert_called()
    # Verify story_ref was passed containing the story issue number
    call_args = mock_renderer.render_task.call_args
    positional_args = call_args[0]
    assert any("#11" in str(arg) for arg in positional_args)


@pytest.mark.asyncio
async def test_sync_skips_existing_issues(
    mock_provider, mock_renderer, plan_json_files, sample_config, repo_context, project_context
):
    """If search returns existing issues, they are not recreated."""
    epics_path, stories_path, tasks_path = plan_json_files
    config = SyncConfig(
        repo="owner/repo",
        project_url="https://github.com/orgs/org/projects/1",
        epics_path=epics_path,
        stories_path=stories_path,
        tasks_path=tasks_path,
        sync_path=sample_config.sync_path,
    )
    mock_provider.get_repo_context.return_value = repo_context
    mock_provider.get_project_context.return_value = project_context
    # Compute plan_id from the plan that will be loaded
    plan = load_plan(epics_path, stories_path, tasks_path)
    plan_id = compute_plan_id(plan)
    # Return existing issue with plan marker
    existing_issue = ExistingIssue(
        id="existing-123",
        number=99,
        body=f"<!-- PLAN_ID: {plan_id} -->\n<!-- EPIC_ID: E-1 -->",
    )
    mock_provider.search_issues.return_value = [existing_issue]
    # Need to create story and task issues since epic exists
    story_ref = IssueRef(id="story-456", number=100, url="https://github.com/owner/repo/issues/100")
    task_ref = IssueRef(id="task-789", number=101, url="https://github.com/owner/repo/issues/101")
    mock_provider.create_issue.side_effect = [story_ref, task_ref]
    mock_provider.add_to_project.return_value = "item-999"
    mock_provider.get_issue_relations.return_value = RelationMap(
        parents={"story-456": None, "task-789": None}, blocked_by={}
    )

    engine = SyncEngine(mock_provider, mock_renderer, config)
    result = await engine.sync()

    # Epic should not be created (exists), but story and task should be created
    assert mock_provider.create_issue.call_count == 2  # story and task
    # Sync map should contain existing epic
    assert "E-1" in result.sync_map.epics
    assert result.sync_map.epics["E-1"].issue_number == 99
    # Story and task should be created
    assert "S-1" in result.sync_map.stories
    assert "T-1" in result.sync_map.tasks


@pytest.mark.asyncio
async def test_sync_updates_bodies_with_cross_refs(
    mock_provider, mock_renderer, plan_json_files, sample_config, repo_context, project_context
):
    """After upsert, all bodies are updated with cross-references."""
    epics_path, stories_path, tasks_path = plan_json_files
    config = SyncConfig(
        repo="owner/repo",
        project_url="https://github.com/orgs/org/projects/1",
        epics_path=epics_path,
        stories_path=stories_path,
        tasks_path=tasks_path,
        sync_path=sample_config.sync_path,
    )
    mock_provider.get_repo_context.return_value = repo_context
    mock_provider.get_project_context.return_value = project_context
    epic_ref = IssueRef(id="epic-123", number=10, url="https://github.com/owner/repo/issues/10")
    story_ref = IssueRef(id="story-456", number=11, url="https://github.com/owner/repo/issues/11")
    task_ref = IssueRef(id="task-789", number=12, url="https://github.com/owner/repo/issues/12")
    mock_provider.create_issue.side_effect = [epic_ref, story_ref, task_ref]
    mock_provider.add_to_project.return_value = "item-999"
    mock_provider.get_issue_relations.return_value = RelationMap(parents={}, blocked_by={})

    engine = SyncEngine(mock_provider, mock_renderer, config)
    await engine.sync()

    # Should update all three issues
    assert mock_provider.update_issue.call_count == 3


@pytest.mark.asyncio
async def test_sync_sets_relations(
    mock_provider, mock_renderer, sample_plan_with_deps, sample_config, repo_context, project_context
):
    """Sync engine sets up sub-issue and blocked-by relationships."""
    _plan, epics_path, stories_path, tasks_path = sample_plan_with_deps
    config = SyncConfig(
        repo="owner/repo",
        project_url="https://github.com/orgs/org/projects/1",
        epics_path=epics_path,
        stories_path=stories_path,
        tasks_path=tasks_path,
        sync_path=sample_config.sync_path,
    )
    mock_provider.get_repo_context.return_value = repo_context
    mock_provider.get_project_context.return_value = project_context
    epic_ref = IssueRef(id="epic-node", number=10, url="https://github.com/owner/repo/issues/10")
    story1_ref = IssueRef(id="story1-node", number=11, url="https://github.com/owner/repo/issues/11")
    story2_ref = IssueRef(id="story2-node", number=12, url="https://github.com/owner/repo/issues/12")
    task1_ref = IssueRef(id="task1-node", number=13, url="https://github.com/owner/repo/issues/13")
    task2_ref = IssueRef(id="task2-node", number=14, url="https://github.com/owner/repo/issues/14")
    mock_provider.create_issue.side_effect = [epic_ref, story1_ref, story2_ref, task1_ref, task2_ref]
    mock_provider.add_to_project.return_value = "item-999"
    mock_provider.get_issue_relations.return_value = RelationMap(
        parents={"story1-node": None, "story2-node": None, "task1-node": None, "task2-node": None}, blocked_by={}
    )

    engine = SyncEngine(mock_provider, mock_renderer, config)
    await engine.sync()

    # Should add sub-issues: stories under epic, tasks under stories
    assert mock_provider.add_sub_issue.call_count >= 2
    # Should add blocked-by: task2 blocked by task1 (cross-story)
    mock_provider.add_blocked_by.assert_called()


@pytest.mark.asyncio
async def test_sync_dry_run_skips_writes(
    mock_provider, mock_renderer, plan_json_files, sample_config, repo_context, project_context
):
    """When dry_run=True, no create/update/set calls are made."""
    epics_path, stories_path, tasks_path = plan_json_files
    config = SyncConfig(
        repo="owner/repo",
        project_url="https://github.com/orgs/org/projects/1",
        epics_path=epics_path,
        stories_path=stories_path,
        tasks_path=tasks_path,
        sync_path=sample_config.sync_path,
        dry_run=True,
    )
    mock_provider.get_repo_context.return_value = repo_context
    mock_provider.get_project_context.return_value = project_context

    engine = SyncEngine(mock_provider, mock_renderer, config)
    result = await engine.sync()

    assert result.dry_run is True
    mock_provider.create_issue.assert_not_called()
    mock_provider.update_issue.assert_not_called()
    mock_provider.set_issue_type.assert_not_called()
    mock_provider.add_to_project.assert_not_called()
    mock_provider.set_project_field.assert_not_called()
    mock_provider.add_sub_issue.assert_not_called()
    mock_provider.add_blocked_by.assert_not_called()


@pytest.mark.asyncio
async def test_sync_dry_run_still_reads(
    mock_provider, mock_renderer, plan_json_files, sample_config, repo_context, project_context
):
    """Dry run still calls check_auth, search, and get contexts."""
    epics_path, stories_path, tasks_path = plan_json_files
    config = SyncConfig(
        repo="owner/repo",
        project_url="https://github.com/orgs/org/projects/1",
        epics_path=epics_path,
        stories_path=stories_path,
        tasks_path=tasks_path,
        sync_path=sample_config.sync_path,
        dry_run=True,
    )
    mock_provider.get_repo_context.return_value = repo_context
    mock_provider.get_project_context.return_value = project_context

    engine = SyncEngine(mock_provider, mock_renderer, config)
    await engine.sync()

    mock_provider.check_auth.assert_called_once()
    mock_provider.get_repo_context.assert_called_once()
    mock_provider.get_project_context.assert_called_once()
    mock_provider.search_issues.assert_called_once()


@pytest.mark.asyncio
async def test_sync_returns_sync_result(
    mock_provider, mock_renderer, plan_json_files, sample_config, repo_context, project_context
):
    """Sync returns proper SyncResult."""
    epics_path, stories_path, tasks_path = plan_json_files
    config = SyncConfig(
        repo="owner/repo",
        project_url="https://github.com/orgs/org/projects/1",
        epics_path=epics_path,
        stories_path=stories_path,
        tasks_path=tasks_path,
        sync_path=sample_config.sync_path,
    )
    mock_provider.get_repo_context.return_value = repo_context
    mock_provider.get_project_context.return_value = project_context
    epic_ref = IssueRef(id="epic-123", number=10, url="https://github.com/owner/repo/issues/10")
    story_ref = IssueRef(id="story-456", number=11, url="https://github.com/owner/repo/issues/11")
    task_ref = IssueRef(id="task-789", number=12, url="https://github.com/owner/repo/issues/12")
    mock_provider.create_issue.side_effect = [epic_ref, story_ref, task_ref]
    mock_provider.add_to_project.return_value = "item-999"
    mock_provider.get_issue_relations.return_value = RelationMap(parents={}, blocked_by={})

    engine = SyncEngine(mock_provider, mock_renderer, config)
    result = await engine.sync()

    assert isinstance(result, SyncResult)
    assert result.epics_created == 1
    assert result.stories_created == 1
    assert result.tasks_created == 1
    assert isinstance(result.sync_map, SyncMap)
    assert result.dry_run is False


@pytest.mark.asyncio
async def test_sync_writes_sync_map(
    mock_provider, mock_renderer, plan_json_files, tmp_path, repo_context, project_context
):
    """Sync writes sync map JSON to sync_path."""
    epics_path, stories_path, tasks_path = plan_json_files
    sync_path = tmp_path / "sync.json"
    config = SyncConfig(
        repo="owner/repo",
        project_url="https://github.com/orgs/org/projects/1",
        epics_path=epics_path,
        stories_path=stories_path,
        tasks_path=tasks_path,
        sync_path=sync_path,
    )
    mock_provider.get_repo_context.return_value = repo_context
    mock_provider.get_project_context.return_value = project_context
    epic_ref = IssueRef(id="epic-123", number=10, url="https://github.com/owner/repo/issues/10")
    story_ref = IssueRef(id="story-456", number=11, url="https://github.com/owner/repo/issues/11")
    task_ref = IssueRef(id="task-789", number=12, url="https://github.com/owner/repo/issues/12")
    mock_provider.create_issue.side_effect = [epic_ref, story_ref, task_ref]
    mock_provider.add_to_project.return_value = "item-999"
    mock_provider.get_issue_relations.return_value = RelationMap(parents={}, blocked_by={})

    engine = SyncEngine(mock_provider, mock_renderer, config)
    await engine.sync()

    assert sync_path.exists()
    content = sync_path.read_text(encoding="utf-8")
    data = json.loads(content)
    assert data["repo"] == "owner/repo"
    assert "epics" in data
    assert "stories" in data
    assert "tasks" in data
