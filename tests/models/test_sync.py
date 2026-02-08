"""Tests for sync models and merge utilities."""

from __future__ import annotations

import pytest

from planpilot.models.sync import SyncEntry, SyncMap, merge_sync_maps


def test_merge_sync_maps_combines_all_entities() -> None:
    first = SyncMap(
        plan_id="plan-a",
        repo="owner/repo",
        project_url="https://github.com/orgs/o/projects/1",
        epics={"E-1": SyncEntry(issue_number=1, url="u1", node_id="n1")},
        stories={"S-1": SyncEntry(issue_number=2, url="u2", node_id="n2")},
        tasks={"T-1": SyncEntry(issue_number=3, url="u3", node_id="n3")},
    )
    second = SyncMap(
        plan_id="plan-b",
        repo="owner/repo",
        project_url="https://github.com/orgs/o/projects/1",
        epics={"E-2": SyncEntry(issue_number=4, url="u4", node_id="n4")},
        stories={"S-2": SyncEntry(issue_number=5, url="u5", node_id="n5")},
        tasks={"T-2": SyncEntry(issue_number=6, url="u6", node_id="n6")},
    )

    merged = merge_sync_maps([first, second])

    assert merged.plan_id.startswith("combined-")
    assert merged.repo == "owner/repo"
    assert merged.project_url == "https://github.com/orgs/o/projects/1"
    assert set(merged.epics) == {"E-1", "E-2"}
    assert set(merged.stories) == {"S-1", "S-2"}
    assert set(merged.tasks) == {"T-1", "T-2"}


def test_merge_sync_maps_rejects_duplicate_ids() -> None:
    first = SyncMap(
        plan_id="plan-a",
        repo="owner/repo",
        project_url="https://github.com/orgs/o/projects/1",
        tasks={"T-1": SyncEntry(issue_number=3, url="u3", node_id="n3")},
    )
    second = SyncMap(
        plan_id="plan-b",
        repo="owner/repo",
        project_url="https://github.com/orgs/o/projects/1",
        tasks={"T-1": SyncEntry(issue_number=9, url="u9", node_id="n9")},
    )

    with pytest.raises(ValueError, match="duplicate task id"):
        merge_sync_maps([first, second])


def test_merge_sync_maps_rejects_incompatible_metadata() -> None:
    first = SyncMap(plan_id="plan-a", repo="owner/repo", project_url="https://github.com/orgs/o/projects/1")
    second = SyncMap(plan_id="plan-b", repo="other/repo", project_url="https://github.com/orgs/o/projects/1")

    with pytest.raises(ValueError, match="incompatible repo"):
        merge_sync_maps([first, second])
