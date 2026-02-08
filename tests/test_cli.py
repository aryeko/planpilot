"""Tests for planpilot CLI."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from planpilot.cli import _build_config, _run_sync, build_parser, main
from planpilot.config import SyncConfig
from planpilot.exceptions import PlanPilotError
from planpilot.models.project import FieldConfig
from planpilot.models.sync import SyncMap, SyncResult


def test_build_parser_requires_mode_flag():
    """Test that parser requires --dry-run or --apply (mutually exclusive)."""
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "--repo",
                "owner/repo",
                "--project-url",
                "https://github.com/orgs/o/projects/1",
                "--epics-path",
                "epics.json",
                "--stories-path",
                "stories.json",
                "--tasks-path",
                "tasks.json",
                "--sync-path",
                "sync.json",
            ]
        )


def test_build_parser_all_args():
    """Test that all arguments are parsed correctly."""
    parser = build_parser()
    args = parser.parse_args(
        [
            "--repo",
            "owner/repo",
            "--project-url",
            "https://github.com/orgs/o/projects/1",
            "--epics-path",
            "epics.json",
            "--stories-path",
            "stories.json",
            "--tasks-path",
            "tasks.json",
            "--sync-path",
            "sync.json",
            "--label",
            "custom-label",
            "--status",
            "In Progress",
            "--priority",
            "P2",
            "--iteration",
            "Sprint 1",
            "--size-field",
            "Effort",
            "--no-size-from-tshirt",
            "--dry-run",
            "--verbose",
        ]
    )
    assert args.repo == "owner/repo"
    assert args.project_url == "https://github.com/orgs/o/projects/1"
    assert args.epics_path == "epics.json"
    assert args.stories_path == "stories.json"
    assert args.tasks_path == "tasks.json"
    assert args.sync_path == "sync.json"
    assert args.label == "custom-label"
    assert args.status == "In Progress"
    assert args.priority == "P2"
    assert args.iteration == "Sprint 1"
    assert args.size_field == "Effort"
    assert args.size_from_tshirt is False
    assert args.dry_run is True
    assert args.apply is False
    assert args.verbose is True


def test_build_parser_defaults():
    """Test that defaults are set correctly."""
    parser = build_parser()
    args = parser.parse_args(
        [
            "--repo",
            "owner/repo",
            "--project-url",
            "https://github.com/orgs/o/projects/1",
            "--epics-path",
            "epics.json",
            "--stories-path",
            "stories.json",
            "--tasks-path",
            "tasks.json",
            "--sync-path",
            "sync.json",
            "--dry-run",
        ]
    )
    assert args.label == "codex"
    assert args.status == "Backlog"
    assert args.priority == "P1"
    assert args.iteration == "active"
    assert args.size_field == "Size"
    assert args.size_from_tshirt is True
    assert args.verbose is False


@pytest.mark.asyncio
async def test_run_sync():
    """Test that _run_sync executes the sync pipeline correctly."""
    config = SyncConfig(
        repo="owner/repo",
        project_url="https://github.com/orgs/o/projects/1",
        epics_path=Path("epics.json"),
        stories_path=Path("stories.json"),
        tasks_path=Path("tasks.json"),
        sync_path=Path("sync.json"),
        dry_run=True,
    )

    mock_result = SyncResult(
        sync_map=SyncMap(plan_id="test", repo="owner/repo", project_url="https://github.com/orgs/o/projects/1"),
        epics_created=1,
        stories_created=2,
        tasks_created=3,
        dry_run=True,
    )

    mock_engine = AsyncMock()
    mock_engine.sync = AsyncMock(return_value=mock_result)

    with (
        patch("planpilot.cli.GitHubProvider"),
        patch("planpilot.cli.GhClient") as mock_client_class,
        patch("planpilot.cli.MarkdownRenderer") as mock_renderer_class,
        patch("planpilot.cli.SyncEngine", return_value=mock_engine),
    ):
        await _run_sync(config)

        mock_client_class.assert_called_once()
        mock_renderer_class.assert_called_once()
        mock_engine.sync.assert_called_once()


def test_build_config_from_args():
    """Test that SyncConfig is built correctly from parsed args."""
    args = argparse.Namespace(
        repo="owner/repo",
        project_url="https://github.com/orgs/o/projects/1",
        epics_path="epics.json",
        stories_path="stories.json",
        tasks_path="tasks.json",
        sync_path="sync.json",
        label="custom-label",
        status="In Progress",
        priority="P2",
        iteration="Sprint 1",
        size_field="Effort",
        size_from_tshirt=False,
        dry_run=True,
        verbose=True,
    )

    config = _build_config(args)

    assert isinstance(config, SyncConfig)
    assert config.repo == "owner/repo"
    assert config.project_url == "https://github.com/orgs/o/projects/1"
    assert config.epics_path == Path("epics.json")
    assert config.stories_path == Path("stories.json")
    assert config.tasks_path == Path("tasks.json")
    assert config.sync_path == Path("sync.json")
    assert config.label == "custom-label"
    assert config.dry_run is True
    assert config.verbose is True
    assert isinstance(config.field_config, FieldConfig)
    assert config.field_config.status == "In Progress"
    assert config.field_config.priority == "P2"
    assert config.field_config.iteration == "Sprint 1"
    assert config.field_config.size_field == "Effort"
    assert config.field_config.size_from_tshirt is False


def test_verbose_configures_logging(capsys):
    """Test that verbose flag sets up logging."""
    with (
        patch("planpilot.cli.asyncio.run") as mock_run,
        patch("planpilot.cli._run_sync"),
        patch(
            "sys.argv",
            [
                "planpilot",
                "--repo",
                "owner/repo",
                "--project-url",
                "https://github.com/orgs/o/projects/1",
                "--epics-path",
                "epics.json",
                "--stories-path",
                "stories.json",
                "--tasks-path",
                "tasks.json",
                "--sync-path",
                "sync.json",
                "--dry-run",
                "--verbose",
            ],
        ),
    ):
        mock_run.return_value = None

        with patch("planpilot.cli.logging.basicConfig") as mock_logging:
            main()
            mock_logging.assert_called_once()
            call_kwargs = mock_logging.call_args[1]
            assert call_kwargs["level"] == logging.DEBUG
            assert call_kwargs["stream"] == sys.stderr


def test_main_returns_zero_on_success(capsys):
    """Test that main returns 0 on successful sync."""
    with (
        patch("planpilot.cli.asyncio.run") as mock_run,
        patch(
            "sys.argv",
            [
                "planpilot",
                "--repo",
                "owner/repo",
                "--project-url",
                "https://github.com/orgs/o/projects/1",
                "--epics-path",
                "epics.json",
                "--stories-path",
                "stories.json",
                "--tasks-path",
                "tasks.json",
                "--sync-path",
                "sync.json",
                "--dry-run",
            ],
        ),
    ):
        mock_run.return_value = None
        result = main()
        assert result == 0


def test_main_returns_nonzero_on_error(capsys):
    """Test that main returns 2 when RuntimeError is raised."""
    with (
        patch("planpilot.cli.asyncio.run") as mock_run,
        patch(
            "sys.argv",
            [
                "planpilot",
                "--repo",
                "owner/repo",
                "--project-url",
                "https://github.com/orgs/o/projects/1",
                "--epics-path",
                "epics.json",
                "--stories-path",
                "stories.json",
                "--tasks-path",
                "tasks.json",
                "--sync-path",
                "sync.json",
                "--dry-run",
            ],
        ),
    ):
        mock_run.side_effect = RuntimeError("test error")
        result = main()
        assert result == 2
        captured = capsys.readouterr()
        assert "error: test error" in captured.err


def test_main_returns_nonzero_on_plan_error(capsys):
    """Test that main returns 2 when PlanPilotError is raised."""
    with (
        patch("planpilot.cli.asyncio.run") as mock_run,
        patch(
            "sys.argv",
            [
                "planpilot",
                "--repo",
                "owner/repo",
                "--project-url",
                "https://github.com/orgs/o/projects/1",
                "--epics-path",
                "epics.json",
                "--stories-path",
                "stories.json",
                "--tasks-path",
                "tasks.json",
                "--sync-path",
                "sync.json",
                "--dry-run",
            ],
        ),
    ):
        mock_run.side_effect = PlanPilotError("plan error")
        result = main()
        assert result == 2
        captured = capsys.readouterr()
        assert "error: plan error" in captured.err
