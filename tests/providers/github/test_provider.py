"""Tests for the GitHub provider implementation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from planpilot.exceptions import AuthenticationError, ProjectURLError, ProviderError
from planpilot.models.project import (
    CreateIssueInput,
    ExistingIssue,
    FieldConfig,
    FieldValue,
    IssueRef,
    ProjectContext,
    RelationMap,
    RepoContext,
)
from planpilot.providers.github.provider import GitHubProvider


@pytest.fixture
def mock_client():
    """Create a mocked GhClient."""
    return AsyncMock()


@pytest.fixture
def provider(mock_client):
    """Create a GitHubProvider with a mocked client."""
    return GitHubProvider(mock_client)


@pytest.mark.asyncio
async def test_check_auth_delegates_to_client(provider, mock_client):
    """Test that check_auth delegates to client.check_auth()."""
    mock_client.check_auth.return_value = None

    await provider.check_auth()

    mock_client.check_auth.assert_called_once()


@pytest.mark.asyncio
async def test_check_auth_raises_on_client_error(provider, mock_client):
    """Test that check_auth raises AuthenticationError when client raises it."""
    mock_client.check_auth.side_effect = AuthenticationError("Auth failed")

    with pytest.raises(AuthenticationError, match="Auth failed"):
        await provider.check_auth()


@pytest.mark.asyncio
async def test_get_repo_context_success(provider, mock_client):
    """Test that get_repo_context returns RepoContext with repo_id, label_id, issue_type_ids."""
    owner, name = "owner", "repo"
    repo = f"{owner}/{name}"
    label = "planpilot"

    mock_client.graphql.return_value = {
        "data": {
            "repository": {
                "id": "repo_node_id",
                "issueTypes": {
                    "nodes": [
                        {"id": "type1", "name": "Epic"},
                        {"id": "type2", "name": "Story"},
                    ]
                },
                "labels": {"nodes": [{"id": "label_node_id", "name": "planpilot"}]},
            }
        }
    }

    result = await provider.get_repo_context(repo, label)

    assert isinstance(result, RepoContext)
    assert result.repo_id == "repo_node_id"
    assert result.label_id == "label_node_id"
    assert result.issue_type_ids == {"Epic": "type1", "Story": "type2"}


@pytest.mark.asyncio
async def test_get_repo_context_creates_label_if_missing(provider, mock_client):
    """Test that get_repo_context creates label if missing, then re-fetches."""
    owner, name = "owner", "repo"
    repo = f"{owner}/{name}"
    label = "planpilot"

    # First call: label not found
    mock_client.graphql.return_value = {
        "data": {
            "repository": {
                "id": "repo_node_id",
                "issueTypes": {"nodes": []},
                "labels": {"nodes": []},
            }
        }
    }

    # Mock the label creation
    mock_client.run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    # Second call: label found after creation
    mock_client.graphql.side_effect = [
        {
            "data": {
                "repository": {
                    "id": "repo_node_id",
                    "issueTypes": {"nodes": []},
                    "labels": {"nodes": []},
                }
            }
        },
        {
            "data": {
                "repository": {
                    "id": "repo_node_id",
                    "issueTypes": {"nodes": []},
                    "labels": {"nodes": [{"id": "label_node_id", "name": "planpilot"}]},
                }
            }
        },
    ]

    result = await provider.get_repo_context(repo, label)

    # Should have called run to create label
    mock_client.run.assert_called_once()
    call_args = mock_client.run.call_args[0][0]
    assert "label" in call_args
    assert "create" in call_args
    assert label in call_args

    # Should have called graphql twice (initial fetch + re-fetch)
    assert mock_client.graphql.call_count == 2
    assert result.label_id == "label_node_id"


@pytest.mark.asyncio
async def test_get_project_context_success(provider, mock_client):
    """Test that get_project_context returns ProjectContext with resolved fields."""
    project_url = "https://github.com/orgs/myorg/projects/1"
    field_config = FieldConfig(
        status="Backlog",
        priority="P1",
        iteration="active",
        size_field="Size",
        size_from_tshirt=True,
    )

    # Mock parse_project_url
    with patch(
        "planpilot.providers.github.provider.parse_project_url",
        return_value=("myorg", 1),
    ):
        # Mock FETCH_PROJECT query (first call) and FETCH_PROJECT_ITEMS query (second call)
        mock_client.graphql.side_effect = [
            {
                "data": {
                    "organization": {
                        "projectV2": {
                            "id": "project_id",
                            "fields": {
                                "nodes": [
                                    {
                                        "id": "status_field_id",
                                        "name": "Status",
                                        "options": [
                                            {"id": "backlog_opt_id", "name": "Backlog"},
                                            {"id": "todo_opt_id", "name": "Todo"},
                                        ],
                                    },
                                    {
                                        "id": "priority_field_id",
                                        "name": "Priority",
                                        "options": [
                                            {"id": "p1_opt_id", "name": "P1"},
                                            {"id": "p2_opt_id", "name": "P2"},
                                        ],
                                    },
                                    {
                                        "id": "iteration_field_id",
                                        "name": "Iteration",
                                        "configuration": {
                                            "iterations": [
                                                {
                                                    "id": "iter1_id",
                                                    "title": "Sprint 1",
                                                    "startDate": "2026-02-01T00:00:00Z",
                                                    "duration": 14,
                                                },
                                                {
                                                    "id": "iter2_id",
                                                    "title": "Sprint 2",
                                                    "startDate": "2026-02-15T00:00:00Z",
                                                    "duration": 14,
                                                },
                                            ]
                                        },
                                    },
                                    {
                                        "id": "size_field_id",
                                        "name": "Size",
                                        "options": [
                                            {"id": "xs_id", "name": "XS"},
                                            {"id": "s_id", "name": "S"},
                                        ],
                                    },
                                ]
                            },
                        }
                    }
                }
            },
            {
                "data": {
                    "node": {
                        "items": {
                            "nodes": [
                                {"id": "item1", "content": {"id": "issue1"}},
                                {"id": "item2", "content": {"id": "issue2"}},
                            ],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                }
            },
        ]

        result = await provider.get_project_context(project_url, field_config)

        assert isinstance(result, ProjectContext)
        assert result.project_id == "project_id"
        assert result.status_field is not None
        assert result.status_field.field_id == "status_field_id"
        assert result.status_field.value.single_select_option_id == "backlog_opt_id"
        assert result.priority_field is not None
        assert result.priority_field.field_id == "priority_field_id"
        assert result.priority_field.value.single_select_option_id == "p1_opt_id"
        assert result.size_field_id == "size_field_id"
        assert result.item_map == {"issue1": "item1", "issue2": "item2"}


@pytest.mark.asyncio
async def test_get_project_context_returns_none_on_error(provider, mock_client):
    """Test that get_project_context returns None if URL is bad or API fails."""
    # Test with invalid URL
    with patch(
        "planpilot.providers.github.provider.parse_project_url",
        side_effect=ProjectURLError("Invalid URL"),
    ):
        result = await provider.get_project_context("bad-url", FieldConfig())
        assert result is None

    # Test with API failure
    with patch(
        "planpilot.providers.github.provider.parse_project_url",
        return_value=("myorg", 1),
    ):
        mock_client.graphql.side_effect = ProviderError("API failed")
        result = await provider.get_project_context("https://github.com/orgs/myorg/projects/1", FieldConfig())
        assert result is None


@pytest.mark.asyncio
async def test_search_issues_single_page(provider, mock_client):
    """Test that search_issues handles single-page results."""
    repo = "owner/repo"
    plan_id = "plan123"
    label = "planpilot"

    mock_client.graphql.return_value = {
        "data": {
            "search": {
                "nodes": [
                    {"id": "issue1", "number": 1, "body": "<!-- PLAN_ID: plan123 -->"},
                    {"id": "issue2", "number": 2, "body": "<!-- PLAN_ID: plan123 -->"},
                ],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            }
        }
    }

    result = await provider.search_issues(repo, plan_id, label)

    assert len(result) == 2
    assert all(isinstance(issue, ExistingIssue) for issue in result)
    assert result[0].id == "issue1"
    assert result[0].number == 1
    assert result[1].id == "issue2"
    assert result[1].number == 2


@pytest.mark.asyncio
async def test_search_issues_paginates(provider, mock_client):
    """Test that search_issues handles multi-page results."""
    repo = "owner/repo"
    plan_id = "plan123"
    label = "planpilot"

    mock_client.graphql.side_effect = [
        {
            "data": {
                "search": {
                    "nodes": [
                        {"id": "issue1", "number": 1, "body": "<!-- PLAN_ID: plan123 -->"},
                    ],
                    "pageInfo": {"hasNextPage": True, "endCursor": "cursor1"},
                }
            }
        },
        {
            "data": {
                "search": {
                    "nodes": [
                        {"id": "issue2", "number": 2, "body": "<!-- PLAN_ID: plan123 -->"},
                    ],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        },
    ]

    result = await provider.search_issues(repo, plan_id, label)

    assert len(result) == 2
    assert mock_client.graphql.call_count == 2


@pytest.mark.asyncio
async def test_create_issue_success(provider, mock_client):
    """Test that create_issue returns IssueRef."""
    issue_input = CreateIssueInput(
        repo_id="repo_id",
        title="Test Issue",
        body="Body text",
        label_ids=["label1"],
    )

    mock_client.graphql_raw.return_value = {
        "data": {
            "createIssue": {
                "issue": {
                    "id": "issue_id",
                    "number": 42,
                    "url": "https://github.com/owner/repo/issues/42",
                }
            }
        }
    }

    result = await provider.create_issue(issue_input)

    assert isinstance(result, IssueRef)
    assert result.id == "issue_id"
    assert result.number == 42
    assert result.url == "https://github.com/owner/repo/issues/42"

    # Verify graphql_raw was called with correct args
    mock_client.graphql_raw.assert_called_once()
    call_args = mock_client.graphql_raw.call_args[0][0]
    assert "api" in call_args
    assert "graphql" in call_args
    assert "-F" in call_args


@pytest.mark.asyncio
async def test_create_issue_raises_on_failure(provider, mock_client):
    """Test that create_issue raises ProviderError on failure."""
    issue_input = CreateIssueInput(repo_id="repo_id", title="Test", body="Body")

    mock_client.graphql_raw.side_effect = ProviderError("Creation failed")

    with pytest.raises(ProviderError, match="Creation failed"):
        await provider.create_issue(issue_input)


@pytest.mark.asyncio
async def test_update_issue_calls_gh_run(provider, mock_client):
    """Test that update_issue calls client.run with correct args."""
    repo = "owner/repo"
    number = 42
    title = "New Title"
    body = "New Body"

    mock_client.run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    await provider.update_issue(repo, number, title, body)

    mock_client.run.assert_called_once()
    call_args = mock_client.run.call_args[0][0]
    assert "issue" in call_args
    assert "edit" in call_args
    assert str(number) in call_args
    assert title in call_args
    assert body in call_args


@pytest.mark.asyncio
async def test_set_issue_type_calls_graphql(provider, mock_client):
    """Test that set_issue_type calls graphql with correct mutation."""
    issue_id = "issue_id"
    type_id = "type_id"

    mock_client.graphql.return_value = {"data": {"updateIssue": {"issue": {"id": issue_id}}}}

    await provider.set_issue_type(issue_id, type_id)

    mock_client.graphql.assert_called_once()
    call_args = mock_client.graphql.call_args
    assert "UPDATE_ISSUE_TYPE" in call_args[0][0] or "updateIssue" in call_args[0][0]
    assert call_args[1]["variables"]["id"] == issue_id
    assert call_args[1]["variables"]["issueTypeId"] == type_id


@pytest.mark.asyncio
async def test_add_to_project_success(provider, mock_client):
    """Test that add_to_project returns item_id."""
    project_id = "project_id"
    issue_id = "issue_id"

    mock_client.graphql.return_value = {"data": {"addProjectV2ItemById": {"item": {"id": "item_id"}}}}

    result = await provider.add_to_project(project_id, issue_id)

    assert result == "item_id"
    mock_client.graphql.assert_called_once()


@pytest.mark.asyncio
async def test_add_to_project_returns_none_on_failure(provider, mock_client):
    """Test that add_to_project returns None on failure."""
    project_id = "project_id"
    issue_id = "issue_id"

    mock_client.graphql.side_effect = ProviderError("Failed")

    result = await provider.add_to_project(project_id, issue_id)

    assert result is None


@pytest.mark.asyncio
async def test_set_project_field_calls_graphql_raw(provider, mock_client):
    """Test that set_project_field calls graphql_raw with correct -F flags."""
    project_id = "project_id"
    item_id = "item_id"
    field_id = "field_id"
    value = FieldValue(single_select_option_id="option_id")

    mock_client.graphql_raw.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": item_id}}}
    }

    await provider.set_project_field(project_id, item_id, field_id, value)

    mock_client.graphql_raw.assert_called_once()
    call_args = mock_client.graphql_raw.call_args[0][0]
    assert "api" in call_args
    assert "graphql" in call_args
    assert "-F" in call_args


@pytest.mark.asyncio
async def test_get_issue_relations_chunks_ids(provider, mock_client):
    """Test that get_issue_relations batches IDs into groups of 50."""
    # Create 75 issue IDs
    issue_ids = [f"issue_{i}" for i in range(75)]

    # Mock responses for 2 batches (50 + 25)
    mock_client.graphql_raw.side_effect = [
        {"data": {"nodes": [{"id": f"issue_{i}", "parent": None, "blockedBy": {"nodes": []}} for i in range(50)]}},
        {"data": {"nodes": [{"id": f"issue_{i}", "parent": None, "blockedBy": {"nodes": []}} for i in range(50, 75)]}},
    ]

    result = await provider.get_issue_relations(issue_ids)

    assert isinstance(result, RelationMap)
    assert len(result.parents) == 75
    assert len(result.blocked_by) == 75
    # Should have called graphql_raw twice (50 + 25)
    assert mock_client.graphql_raw.call_count == 2


@pytest.mark.asyncio
async def test_get_issue_relations_builds_maps(provider, mock_client):
    """Test that get_issue_relations correctly builds parent and blocked_by maps."""
    issue_ids = ["issue1", "issue2", "issue3"]

    mock_client.graphql_raw.return_value = {
        "data": {
            "nodes": [
                {
                    "id": "issue1",
                    "parent": {"id": "parent1"},
                    "blockedBy": {"nodes": [{"id": "blocker1"}]},
                },
                {"id": "issue2", "parent": None, "blockedBy": {"nodes": []}},
                {
                    "id": "issue3",
                    "parent": {"id": "parent2"},
                    "blockedBy": {"nodes": [{"id": "blocker2"}, {"id": "blocker3"}]},
                },
            ]
        }
    }

    result = await provider.get_issue_relations(issue_ids)

    assert result.parents["issue1"] == "parent1"
    assert result.parents["issue2"] is None
    assert result.parents["issue3"] == "parent2"
    assert result.blocked_by["issue1"] == {"blocker1"}
    assert result.blocked_by["issue2"] == set()
    assert result.blocked_by["issue3"] == {"blocker2", "blocker3"}


@pytest.mark.asyncio
async def test_add_sub_issue_calls_graphql(provider, mock_client):
    """Test that add_sub_issue calls graphql with ADD_SUB_ISSUE."""
    parent_id = "parent_id"
    child_id = "child_id"

    mock_client.graphql.return_value = {"data": {"addSubIssue": {"issue": {"id": parent_id}}}}

    await provider.add_sub_issue(parent_id, child_id)

    mock_client.graphql.assert_called_once()
    call_args = mock_client.graphql.call_args
    assert "ADD_SUB_ISSUE" in call_args[0][0] or "addSubIssue" in call_args[0][0]
    assert call_args[1]["variables"]["issueId"] == parent_id
    assert call_args[1]["variables"]["subIssueId"] == child_id


@pytest.mark.asyncio
async def test_add_blocked_by_calls_graphql(provider, mock_client):
    """Test that add_blocked_by calls graphql with ADD_BLOCKED_BY."""
    issue_id = "issue_id"
    blocker_id = "blocker_id"

    mock_client.graphql.return_value = {"data": {"addBlockedBy": {"issue": {"id": issue_id}}}}

    await provider.add_blocked_by(issue_id, blocker_id)

    mock_client.graphql.assert_called_once()
    call_args = mock_client.graphql.call_args
    assert "ADD_BLOCKED_BY" in call_args[0][0] or "addBlockedBy" in call_args[0][0]
    assert call_args[1]["variables"]["issueId"] == issue_id
    assert call_args[1]["variables"]["blockingIssueId"] == blocker_id


def test_build_issue_map_basic(provider):
    """Test that build_issue_map extracts entity markers into nested dict."""
    issues = [
        ExistingIssue(
            id="i1",
            number=1,
            body="<!-- PLAN_ID: plan1 -->\n<!-- EPIC_ID: E-1 -->",
        ),
        ExistingIssue(
            id="i2",
            number=2,
            body="<!-- PLAN_ID: plan1 -->\n<!-- STORY_ID: S-1 -->",
        ),
        ExistingIssue(
            id="i3",
            number=3,
            body="<!-- PLAN_ID: plan1 -->\n<!-- TASK_ID: T-1 -->",
        ),
    ]
    result = provider.build_issue_map(issues, "plan1")
    assert result["epics"] == {"E-1": {"id": "i1", "number": 1}}
    assert result["stories"] == {"S-1": {"id": "i2", "number": 2}}
    assert result["tasks"] == {"T-1": {"id": "i3", "number": 3}}


def test_build_issue_map_filters_by_plan_id(provider):
    """Test that build_issue_map skips issues with non-matching plan_id."""
    issues = [
        ExistingIssue(
            id="i1",
            number=1,
            body="<!-- PLAN_ID: plan1 -->\n<!-- EPIC_ID: E-1 -->",
        ),
        ExistingIssue(
            id="i2",
            number=2,
            body="<!-- PLAN_ID: other -->\n<!-- EPIC_ID: E-2 -->",
        ),
    ]
    result = provider.build_issue_map(issues, "plan1")
    assert "E-1" in result["epics"]
    assert "E-2" not in result["epics"]


def test_resolve_option_id_found(provider):
    """Test that resolve_option_id returns matching option ID (case-insensitive)."""
    options = [
        {"id": "opt1", "name": "High"},
        {"id": "opt2", "name": "Low"},
    ]
    assert provider.resolve_option_id(options, "high") == "opt1"
    assert provider.resolve_option_id(options, "LOW") == "opt2"


def test_resolve_option_id_not_found(provider):
    """Test that resolve_option_id returns None when no match."""
    options = [{"id": "opt1", "name": "High"}]
    assert provider.resolve_option_id(options, "Medium") is None


def test_resolve_option_id_none_name(provider):
    """Test that resolve_option_id returns None when name is None."""
    options = [{"id": "opt1", "name": "High"}]
    assert provider.resolve_option_id(options, None) is None


@pytest.mark.asyncio
async def test_get_project_context_returns_none_on_unexpected_error(provider, mock_client):
    """Test that get_project_context returns None on unexpected (non-Provider) errors."""
    with patch(
        "planpilot.providers.github.provider.parse_project_url",
        return_value=("myorg", 1),
    ):
        mock_client.graphql.side_effect = RuntimeError("Unexpected")
        result = await provider.get_project_context("https://github.com/orgs/myorg/projects/1", FieldConfig())
        assert result is None


@pytest.mark.asyncio
async def test_set_project_field_iteration_value(provider, mock_client):
    """Test that set_project_field handles iteration_id values."""
    mock_client.graphql_raw.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "item_id"}}}
    }

    value = FieldValue(iteration_id="iter-123")
    await provider.set_project_field("project_id", "item_id", "field_id", value)

    mock_client.graphql_raw.assert_called_once()
    call_args = mock_client.graphql_raw.call_args[0][0]
    # Verify the iteration value was serialized
    value_str = " ".join(call_args)
    assert "iterationId" in value_str
