"""Tests for GitHub mapper functions."""

from __future__ import annotations

import pytest

from planpilot.exceptions import ProjectURLError
from planpilot.providers.github.mapper import (
    build_blocked_by_map,
    build_issue_mapping,
    build_parent_map,
    build_project_item_map,
    parse_markers,
    parse_project_url,
    resolve_option_id,
)


def test_parse_markers_extracts_all_markers():
    """Test that parse_markers extracts PLAN_ID, EPIC_ID, STORY_ID, TASK_ID."""
    body = """
    Some issue body text
    <!-- PLAN_ID: plan123 -->
    <!-- EPIC_ID: epic456 -->
    <!-- STORY_ID: story789 -->
    <!-- TASK_ID: task101 -->
    More text
    """
    result = parse_markers(body)
    assert result["plan_id"] == "plan123"
    assert result["epic_id"] == "epic456"
    assert result["story_id"] == "story789"
    assert result["task_id"] == "task101"


def test_parse_markers_returns_empty_strings_for_missing_markers():
    """Test that parse_markers returns empty strings for missing markers."""
    body = "Just some text without markers"
    result = parse_markers(body)
    assert result["plan_id"] == ""
    assert result["epic_id"] == ""
    assert result["story_id"] == ""
    assert result["task_id"] == ""


def test_parse_markers_partial_markers():
    """Test that parse_markers handles partial markers correctly."""
    body = """
    <!-- PLAN_ID: plan123 -->
    <!-- STORY_ID: story789 -->
    """
    result = parse_markers(body)
    assert result["plan_id"] == "plan123"
    assert result["epic_id"] == ""
    assert result["story_id"] == "story789"
    assert result["task_id"] == ""


def test_parse_markers_handles_whitespace():
    """Test that parse_markers trims whitespace from marker values."""
    body = """
    <!-- PLAN_ID:   plan123   -->
    <!-- EPIC_ID: epic456 -->
    """
    result = parse_markers(body)
    assert result["plan_id"] == "plan123"
    assert result["epic_id"] == "epic456"


def test_parse_markers_malformed_marker():
    """Test that parse_markers handles malformed markers (missing closing)."""
    body = """
    <!-- PLAN_ID: plan123
    <!-- EPIC_ID: epic456 -->
    """
    result = parse_markers(body)
    assert result["plan_id"] == ""  # Should be empty due to malformed marker
    assert result["epic_id"] == "epic456"


def test_build_issue_mapping_filters_by_plan_id():
    """Test that build_issue_mapping filters issues by plan_id."""
    issues = [
        {
            "id": "issue1",
            "number": 1,
            "body": "<!-- PLAN_ID: plan123 -->\n<!-- EPIC_ID: epic1 -->",
        },
        {
            "id": "issue2",
            "number": 2,
            "body": "<!-- PLAN_ID: plan456 -->\n<!-- EPIC_ID: epic2 -->",
        },
        {
            "id": "issue3",
            "number": 3,
            "body": "<!-- PLAN_ID: plan123 -->\n<!-- STORY_ID: story1 -->",
        },
    ]
    result = build_issue_mapping(issues, plan_id="plan123")
    assert "epic1" in result["epics"]
    assert "epic2" not in result["epics"]
    assert "story1" in result["stories"]
    assert len(result["epics"]) == 1
    assert len(result["stories"]) == 1
    assert len(result["tasks"]) == 0


def test_build_issue_mapping_without_plan_id():
    """Test that build_issue_mapping includes all issues when plan_id is empty."""
    issues = [
        {
            "id": "issue1",
            "number": 1,
            "body": "<!-- PLAN_ID: plan123 -->\n<!-- EPIC_ID: epic1 -->",
        },
        {
            "id": "issue2",
            "number": 2,
            "body": "<!-- PLAN_ID: plan456 -->\n<!-- EPIC_ID: epic2 -->",
        },
    ]
    result = build_issue_mapping(issues, plan_id="")
    assert "epic1" in result["epics"]
    assert "epic2" in result["epics"]
    assert len(result["epics"]) == 2


def test_build_issue_mapping_categorizes_correctly():
    """Test that build_issue_mapping categorizes epics, stories, and tasks."""
    issues = [
        {
            "id": "issue1",
            "number": 1,
            "body": "<!-- EPIC_ID: epic1 -->",
        },
        {
            "id": "issue2",
            "number": 2,
            "body": "<!-- STORY_ID: story1 -->",
        },
        {
            "id": "issue3",
            "number": 3,
            "body": "<!-- TASK_ID: task1 -->",
        },
    ]
    result = build_issue_mapping(issues)
    assert result["epics"]["epic1"]["id"] == "issue1"
    assert result["epics"]["epic1"]["number"] == 1
    assert result["stories"]["story1"]["id"] == "issue2"
    assert result["stories"]["story1"]["number"] == 2
    assert result["tasks"]["task1"]["id"] == "issue3"
    assert result["tasks"]["task1"]["number"] == 3


def test_build_project_item_map():
    """Test that build_project_item_map maps content IDs to item IDs."""
    items = [
        {"id": "item1", "content": {"id": "issue1"}},
        {"id": "item2", "content": {"id": "issue2"}},
        {"id": "item3", "content": {"id": "issue3"}},
    ]
    result = build_project_item_map(items)
    assert result["issue1"] == "item1"
    assert result["issue2"] == "item2"
    assert result["issue3"] == "item3"


def test_build_project_item_map_skips_missing_content():
    """Test that build_project_item_map skips items without content."""
    items = [
        {"id": "item1", "content": {"id": "issue1"}},
        {"id": "item2", "content": None},
        {"id": "item3"},  # Missing content key
    ]
    result = build_project_item_map(items)
    assert result["issue1"] == "item1"
    assert "item2" not in result.values()
    assert len(result) == 1


def test_resolve_option_id_case_insensitive():
    """Test that resolve_option_id performs case-insensitive matching."""
    options = [
        {"id": "opt1", "name": "Option One"},
        {"id": "opt2", "name": "Option Two"},
    ]
    assert resolve_option_id(options, "option one") == "opt1"
    assert resolve_option_id(options, "OPTION TWO") == "opt2"
    assert resolve_option_id(options, "OpTiOn OnE") == "opt1"


def test_resolve_option_id_returns_none_for_no_match():
    """Test that resolve_option_id returns None when no match is found."""
    options = [
        {"id": "opt1", "name": "Option One"},
    ]
    assert resolve_option_id(options, "NonExistent") is None


def test_resolve_option_id_returns_none_for_none_name():
    """Test that resolve_option_id returns None when name is None."""
    options = [
        {"id": "opt1", "name": "Option One"},
    ]
    assert resolve_option_id(options, None) is None


def test_resolve_option_id_returns_none_for_empty_name():
    """Test that resolve_option_id returns None when name is empty string."""
    options = [
        {"id": "opt1", "name": "Option One"},
    ]
    assert resolve_option_id(options, "") is None


def test_parse_project_url_valid():
    """Test that parse_project_url extracts org and number from valid URL."""
    url = "https://github.com/orgs/myorg/projects/42"
    org, number = parse_project_url(url)
    assert org == "myorg"
    assert number == 42


def test_parse_project_url_with_trailing_slash():
    """Test that parse_project_url handles trailing slash."""
    url = "https://github.com/orgs/myorg/projects/42/"
    org, number = parse_project_url(url)
    assert org == "myorg"
    assert number == 42


def test_parse_project_url_raises_on_invalid_format():
    """Test that parse_project_url raises ProjectURLError on invalid format."""
    with pytest.raises(ProjectURLError, match="Invalid project URL"):
        parse_project_url("https://github.com/myorg/projects/42")

    with pytest.raises(ProjectURLError):
        parse_project_url("not-a-url")

    with pytest.raises(ProjectURLError):
        parse_project_url("https://github.com/orgs/myorg/projects/abc")  # Non-numeric


def test_build_parent_map():
    """Test that build_parent_map maps issue IDs to parent IDs."""
    nodes = [
        {"id": "issue1", "parent": {"id": "parent1"}},
        {"id": "issue2", "parent": None},
        {"id": "issue3", "parent": {"id": "parent2"}},
    ]
    result = build_parent_map(nodes)
    assert result["issue1"] == "parent1"
    assert result["issue2"] is None
    assert result["issue3"] == "parent2"


def test_build_blocked_by_map():
    """Test that build_blocked_by_map maps issue IDs to sets of blocker IDs."""
    nodes = [
        {
            "id": "issue1",
            "blockedBy": {"nodes": [{"id": "blocker1"}, {"id": "blocker2"}]},
        },
        {"id": "issue2", "blockedBy": {"nodes": []}},
        {
            "id": "issue3",
            "blockedBy": {"nodes": [{"id": "blocker3"}]},
        },
    ]
    result = build_blocked_by_map(nodes)
    assert result["issue1"] == {"blocker1", "blocker2"}
    assert result["issue2"] == set()
    assert result["issue3"] == {"blocker3"}


def test_build_blocked_by_map_handles_missing_blocked_by():
    """Test that build_blocked_by_map handles missing blockedBy field."""
    nodes = [
        {"id": "issue1", "blockedBy": {"nodes": [{"id": "blocker1"}]}},
        {"id": "issue2"},  # Missing blockedBy
    ]
    result = build_blocked_by_map(nodes)
    assert result["issue1"] == {"blocker1"}
    assert result["issue2"] == set()
