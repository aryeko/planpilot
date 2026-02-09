import pytest

from planpilot_v2.contracts.exceptions import ProjectURLError
from planpilot_v2.providers.github.mapper import (
    build_blocked_by_map,
    build_parent_map,
    parse_project_url,
    resolve_option_id,
)


def test_parse_project_url_org_and_user() -> None:
    assert parse_project_url("https://github.com/orgs/acme/projects/12") == ("org", "acme", 12)
    assert parse_project_url("https://github.com/users/jane/projects/7") == ("user", "jane", 7)


def test_parse_project_url_raises_on_invalid() -> None:
    with pytest.raises(ProjectURLError):
        parse_project_url("https://github.com/acme/projects/12")


def test_resolve_option_id_case_insensitive() -> None:
    options = [{"id": "1", "name": "Backlog"}, {"id": "2", "name": "In Progress"}]
    assert resolve_option_id(options, "in progress") == "2"
    assert resolve_option_id(options, "missing") is None
    assert resolve_option_id(options, "  ") is None


def test_build_parent_map() -> None:
    data = {
        "nodes": [
            "bad-node",
            {"id": "A", "parent": {"id": "P1"}},
            {"id": "B", "parent": None},
            {"id": "D", "parent": {}},
            {"id": "C", "parent": {"id": "P2"}},
        ]
    }

    assert build_parent_map(data) == {"A": "P1", "C": "P2"}


def test_build_blocked_by_map() -> None:
    data = {
        "nodes": [
            123,
            {"id": "A", "blockedBy": {"nodes": [{"id": "X"}, {"id": "Y"}]}},
            {"id": "B", "blockedBy": {"nodes": []}},
            {"id": "C", "blockedBy": None},
        ]
    }

    assert build_blocked_by_map(data) == {"A": {"X", "Y"}}
