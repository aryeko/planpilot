"""Tests for slice functionality."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from planpilot.slice import slice_cli, slice_epics_for_sync


def test_slice_filters_cross_epic_dependencies():
    """Test that slice_epics_for_sync filters cross-epic task dependencies."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        epics_path = root / "epics.json"
        stories_path = root / "stories.json"
        tasks_path = root / "tasks.json"
        out_dir = root / "tmp"

        epics = [
            {"id": "E-1", "story_ids": ["S-1"]},
            {"id": "E-2", "story_ids": ["S-2"]},
        ]
        stories = [
            {"id": "S-1", "epic_id": "E-1", "task_ids": ["T-1"]},
            {"id": "S-2", "epic_id": "E-2", "task_ids": ["T-2"]},
        ]
        tasks = [
            {"id": "T-1", "story_id": "S-1", "depends_on": ["T-2"]},
            {"id": "T-2", "story_id": "S-2", "depends_on": []},
        ]

        epics_path.write_text(json.dumps(epics), encoding="utf-8")
        stories_path.write_text(json.dumps(stories), encoding="utf-8")
        tasks_path.write_text(json.dumps(tasks), encoding="utf-8")

        results = slice_epics_for_sync(epics_path, stories_path, tasks_path, out_dir)
        assert len(results) == 2

        # E-1 slice: T-1 depends on T-2, but T-2 is in E-2, so dependency removed
        e1_tasks = json.loads((out_dir / "tasks.E-1.json").read_text(encoding="utf-8"))
        assert e1_tasks[0]["depends_on"] == []

        # E-2 slice: T-2 has no cross-epic dependencies
        e2_tasks = json.loads((out_dir / "tasks.E-2.json").read_text(encoding="utf-8"))
        assert e2_tasks[0]["depends_on"] == []


def test_slice_empty_epics_produces_no_output():
    """Test that slice_epics_for_sync with empty epics list produces no output."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        epics_path = root / "epics.json"
        stories_path = root / "stories.json"
        tasks_path = root / "tasks.json"
        out_dir = root / "tmp"

        epics_path.write_text(json.dumps([]), encoding="utf-8")
        stories_path.write_text(json.dumps([]), encoding="utf-8")
        tasks_path.write_text(json.dumps([]), encoding="utf-8")

        results = slice_epics_for_sync(epics_path, stories_path, tasks_path, out_dir)
        assert results == []

        # Empty epics results in no output files
        assert not list(out_dir.glob("epics.*.json"))


def test_slice_missing_story_is_skipped():
    """Test that slice_epics_for_sync skips stories missing from stories.json."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        epics_path = root / "epics.json"
        stories_path = root / "stories.json"
        tasks_path = root / "tasks.json"
        out_dir = root / "tmp"

        # Epic references S-1, but S-1 is missing from stories.json
        epics = [{"id": "E-1", "story_ids": ["S-1", "S-missing"]}]
        stories = [{"id": "S-1", "epic_id": "E-1", "task_ids": ["T-1"]}]
        tasks = [{"id": "T-1", "story_id": "S-1", "depends_on": []}]

        epics_path.write_text(json.dumps(epics), encoding="utf-8")
        stories_path.write_text(json.dumps(stories), encoding="utf-8")
        tasks_path.write_text(json.dumps(tasks), encoding="utf-8")

        # Should not raise; missing story is skipped
        results = slice_epics_for_sync(epics_path, stories_path, tasks_path, out_dir)
        assert len(results) == 1

        e1_stories = json.loads((out_dir / "stories.E-1.json").read_text(encoding="utf-8"))
        assert len(e1_stories) == 1
        assert e1_stories[0]["id"] == "S-1"


def test_slice_task_without_depends_on_key():
    """Test that slice_epics_for_sync handles tasks without depends_on key."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        epics_path = root / "epics.json"
        stories_path = root / "stories.json"
        tasks_path = root / "tasks.json"
        out_dir = root / "tmp"

        epics = [{"id": "E-1", "story_ids": ["S-1"]}]
        stories = [{"id": "S-1", "epic_id": "E-1", "task_ids": ["T-1"]}]
        # Task without depends_on key
        tasks = [{"id": "T-1", "story_id": "S-1"}]

        epics_path.write_text(json.dumps(epics), encoding="utf-8")
        stories_path.write_text(json.dumps(stories), encoding="utf-8")
        tasks_path.write_text(json.dumps(tasks), encoding="utf-8")

        # Should not raise; depends_on defaults to empty list
        results = slice_epics_for_sync(epics_path, stories_path, tasks_path, out_dir)
        assert len(results) == 1

        e1_tasks = json.loads((out_dir / "tasks.E-1.json").read_text(encoding="utf-8"))
        assert len(e1_tasks) == 1
        assert e1_tasks[0]["depends_on"] == []


def test_slice_single_epic_produces_identical_output():
    """Test that a single-epic plan produces identical output (no filtering)."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        epics_path = root / "epics.json"
        stories_path = root / "stories.json"
        tasks_path = root / "tasks.json"
        out_dir = root / "tmp"

        epics = [{"id": "E-1", "story_ids": ["S-1", "S-2"]}]
        stories = [
            {"id": "S-1", "epic_id": "E-1", "task_ids": ["T-1"]},
            {"id": "S-2", "epic_id": "E-1", "task_ids": ["T-2"]},
        ]
        tasks = [
            {"id": "T-1", "story_id": "S-1", "depends_on": ["T-2"]},
            {"id": "T-2", "story_id": "S-2", "depends_on": []},
        ]

        epics_path.write_text(json.dumps(epics), encoding="utf-8")
        stories_path.write_text(json.dumps(stories), encoding="utf-8")
        tasks_path.write_text(json.dumps(tasks), encoding="utf-8")

        results = slice_epics_for_sync(epics_path, stories_path, tasks_path, out_dir)
        assert len(results) == 1

        # Single-epic slice should keep T-1's cross-story (but same-epic) dependency
        e1_tasks = json.loads((out_dir / "tasks.E-1.json").read_text(encoding="utf-8"))
        assert e1_tasks[0]["depends_on"] == ["T-2"]
        assert e1_tasks[1]["depends_on"] == []


def test_slice_cli_file_not_found():
    """Test that slice_cli returns 1 when a file is missing."""
    with patch(
        "sys.argv",
        [
            "planpilot-slice",
            "--epics-path",
            "/nonexistent/epics.json",
            "--stories-path",
            "/nonexistent/stories.json",
            "--tasks-path",
            "/nonexistent/tasks.json",
        ],
    ):
        assert slice_cli() == 1


def test_slice_cli_invalid_json():
    """Test that slice_cli returns 1 on invalid JSON input."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        bad_file = root / "bad.json"
        bad_file.write_text("not valid json", encoding="utf-8")

        with patch(
            "sys.argv",
            [
                "planpilot-slice",
                "--epics-path",
                str(bad_file),
                "--stories-path",
                str(bad_file),
                "--tasks-path",
                str(bad_file),
            ],
        ):
            assert slice_cli() == 1


def test_slice_cli_success():
    """Test that slice_cli returns 0 on valid inputs."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        epics_path = root / "epics.json"
        stories_path = root / "stories.json"
        tasks_path = root / "tasks.json"
        out_dir = root / "out"

        epics_path.write_text(json.dumps([{"id": "E-1", "story_ids": ["S-1"]}]), encoding="utf-8")
        stories_path.write_text(json.dumps([{"id": "S-1", "epic_id": "E-1", "task_ids": ["T-1"]}]), encoding="utf-8")
        tasks_path.write_text(json.dumps([{"id": "T-1", "story_id": "S-1", "depends_on": []}]), encoding="utf-8")

        with patch(
            "sys.argv",
            [
                "planpilot-slice",
                "--epics-path",
                str(epics_path),
                "--stories-path",
                str(stories_path),
                "--tasks-path",
                str(tasks_path),
                "--out-dir",
                str(out_dir),
            ],
        ):
            assert slice_cli() == 0


def test_slice_cli_unexpected_error():
    """Test that slice_cli returns 1 on unexpected errors."""
    with (
        patch(
            "sys.argv",
            ["planpilot-slice", "--epics-path", "e.json", "--stories-path", "s.json", "--tasks-path", "t.json"],
        ),
        patch("planpilot.slice.slice_epics_for_sync", side_effect=RuntimeError("boom")),
    ):
        assert slice_cli() == 1


def test_slice_uses_safe_filename_for_unsafe_epic_id():
    """Unsafe epic IDs are sanitized for output filenames."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        epics_path = root / "epics.json"
        stories_path = root / "stories.json"
        tasks_path = root / "tasks.json"
        out_dir = root / "tmp"

        epics = [{"id": "epic:/\\*?<>|", "story_ids": ["S-1"]}]
        stories = [{"id": "S-1", "epic_id": "epic:/\\*?<>|", "task_ids": ["T-1"]}]
        tasks = [{"id": "T-1", "story_id": "S-1", "depends_on": []}]

        epics_path.write_text(json.dumps(epics), encoding="utf-8")
        stories_path.write_text(json.dumps(stories), encoding="utf-8")
        tasks_path.write_text(json.dumps(tasks), encoding="utf-8")

        results = slice_epics_for_sync(epics_path, stories_path, tasks_path, out_dir)

        assert len(results) == 1
        assert results[0].epics_path.name.startswith("epics.epic")
        assert results[0].epics_path.exists()
        assert ":" not in results[0].epics_path.name
        assert "/" not in results[0].epics_path.name


def test_slice_reports_dropped_cross_epic_dependencies(caplog: pytest.LogCaptureFixture):
    """Dropped cross-epic deps are logged and returned in SliceResult."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        epics_path = root / "epics.json"
        stories_path = root / "stories.json"
        tasks_path = root / "tasks.json"
        out_dir = root / "tmp"

        epics = [
            {"id": "E-1", "story_ids": ["S-1"]},
            {"id": "E-2", "story_ids": ["S-2"]},
        ]
        stories = [
            {"id": "S-1", "epic_id": "E-1", "task_ids": ["T-1"]},
            {"id": "S-2", "epic_id": "E-2", "task_ids": ["T-2"]},
        ]
        tasks = [
            {"id": "T-1", "story_id": "S-1", "depends_on": ["T-2"]},
            {"id": "T-2", "story_id": "S-2", "depends_on": []},
        ]

        epics_path.write_text(json.dumps(epics), encoding="utf-8")
        stories_path.write_text(json.dumps(stories), encoding="utf-8")
        tasks_path.write_text(json.dumps(tasks), encoding="utf-8")

        caplog.set_level(logging.WARNING)
        results = slice_epics_for_sync(epics_path, stories_path, tasks_path, out_dir)

        assert any("dropped 1 cross-epic dep(s)" in msg for msg in caplog.messages)
        e1_result = next(result for result in results if result.epic_id == "E-1")
        assert e1_result.dropped_deps == [("T-1", "T-2")]


def test_slice_rejects_non_array_epics():
    """epics must be a JSON array."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        epics_path = root / "epics.json"
        stories_path = root / "stories.json"
        tasks_path = root / "tasks.json"

        epics_path.write_text(json.dumps({}), encoding="utf-8")
        stories_path.write_text(json.dumps([]), encoding="utf-8")
        tasks_path.write_text(json.dumps([]), encoding="utf-8")

        with pytest.raises(ValueError, match="epics: expected a JSON array"):
            slice_epics_for_sync(epics_path, stories_path, tasks_path, root / "tmp")


def test_slice_rejects_missing_story_id_key():
    """stories require both id and epic_id keys."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        epics_path = root / "epics.json"
        stories_path = root / "stories.json"
        tasks_path = root / "tasks.json"

        epics_path.write_text(json.dumps([{"id": "E-1", "story_ids": []}]), encoding="utf-8")
        stories_path.write_text(json.dumps([{"epic_id": "E-1"}]), encoding="utf-8")
        tasks_path.write_text(json.dumps([]), encoding="utf-8")

        with pytest.raises(ValueError, match=r"stories\[0\]: missing required key 'id'"):
            slice_epics_for_sync(epics_path, stories_path, tasks_path, root / "tmp")


def test_slice_rejects_missing_task_story_id_key():
    """tasks require story_id key."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        epics_path = root / "epics.json"
        stories_path = root / "stories.json"
        tasks_path = root / "tasks.json"

        epics_path.write_text(json.dumps([{"id": "E-1", "story_ids": ["S-1"]}]), encoding="utf-8")
        stories_path.write_text(json.dumps([{"id": "S-1", "epic_id": "E-1", "task_ids": ["T-1"]}]), encoding="utf-8")
        tasks_path.write_text(json.dumps([{"id": "T-1"}]), encoding="utf-8")

        with pytest.raises(ValueError, match=r"tasks\[0\]: missing required key 'story_id'"):
            slice_epics_for_sync(epics_path, stories_path, tasks_path, root / "tmp")
