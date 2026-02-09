from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pytest

from planpilot import (
    AuthenticationError,
    ConfigError,
    PlanItemType,
    PlanLoadError,
    PlanPilotConfig,
    PlanValidationError,
    ProviderError,
    SyncEntry,
    SyncError,
    SyncMap,
    SyncResult,
)
from planpilot.cli import _format_summary, _run_sync, build_parser, main


def _make_config(tmp_path: Path) -> PlanPilotConfig:
    return PlanPilotConfig(
        provider="github",
        target="owner/repo",
        board_url="https://github.com/orgs/owner/projects/1",
        plan_paths={"unified": tmp_path / "plan.json"},
        sync_path=tmp_path / "sync-map.json",
    )


def _make_args(*, dry_run: bool) -> argparse.Namespace:
    return argparse.Namespace(
        command="sync",
        config="/tmp/planpilot.json",
        dry_run=dry_run,
        apply=not dry_run,
        verbose=False,
    )


def _make_sync_result(*, dry_run: bool, sync_path: Path) -> tuple[SyncResult, PlanPilotConfig]:
    config = PlanPilotConfig(
        provider="github",
        target="owner/repo",
        board_url="https://github.com/orgs/owner/projects/1",
        plan_paths={"unified": Path("/tmp/plan.json")},
        sync_path=sync_path,
    )
    sync_map = SyncMap(
        plan_id="a1b2c3d4e5f6",
        target=config.target,
        board_url=config.board_url,
        entries={
            "E1": SyncEntry(
                id="1", key="#42", url="https://github.com/owner/repo/issues/42", item_type=PlanItemType.EPIC
            ),
            "S1": SyncEntry(
                id="2", key="#43", url="https://github.com/owner/repo/issues/43", item_type=PlanItemType.STORY
            ),
            "T1": SyncEntry(
                id="3", key="#44", url="https://github.com/owner/repo/issues/44", item_type=PlanItemType.TASK
            ),
        },
    )
    result = SyncResult(
        sync_map=sync_map,
        items_created={
            PlanItemType.EPIC: 1,
            PlanItemType.STORY: 0,
            PlanItemType.TASK: 0,
        },
        dry_run=dry_run,
    )
    return result, config


def test_build_parser_requires_sync_subcommand() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as exc:
        parser.parse_args([])

    assert exc.value.code == 2


def test_build_parser_sync_requires_mode_and_config() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["sync", "--config", "planpilot.json"])

    assert exc.value.code == 2


@pytest.mark.parametrize("mode", ["--dry-run", "--apply"])
def test_build_parser_sync_accepts_required_arguments(mode: str) -> None:
    parser = build_parser()

    args = parser.parse_args(["sync", "--config", "planpilot.json", mode])

    assert args.command == "sync"
    assert args.config == "planpilot.json"
    assert args.verbose is False


def test_build_parser_version_prints_and_exits(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--version"])

    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "planpilot" in captured.out


@pytest.mark.asyncio
async def test_run_sync_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args = _make_args(dry_run=True)
    config = _make_config(tmp_path)
    result, _ = _make_sync_result(dry_run=True, sync_path=config.sync_path)

    class _FakeSDK:
        async def sync(self, *, dry_run: bool) -> SyncResult:
            assert dry_run is True
            return result

    async def _fake_from_config(input_config: PlanPilotConfig):
        assert input_config == config
        return _FakeSDK()

    monkeypatch.setattr("planpilot.cli.load_config", lambda _: config)
    monkeypatch.setattr("planpilot.cli.PlanPilot.from_config", _fake_from_config)

    actual = await _run_sync(args)

    assert actual == result


def test_main_returns_zero_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("planpilot.cli.asyncio.run", lambda _: None)

    exit_code = main(["sync", "--config", "planpilot.json", "--dry-run"])

    assert exit_code == 0


def test_main_enables_verbose_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("planpilot.cli.asyncio.run", lambda _: None)

    captured: dict[str, object] = {}

    def _fake_basic_config(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr("planpilot.cli.logging.basicConfig", _fake_basic_config)

    main(["sync", "--config", "planpilot.json", "--dry-run", "--verbose"])

    assert captured["level"] == logging.DEBUG
    assert captured["stream"] == sys.stderr


@pytest.mark.parametrize(
    ("error", "exit_code"),
    [
        (ConfigError("bad config"), 3),
        (PlanLoadError("bad plan"), 3),
        (PlanValidationError("bad validation"), 3),
        (AuthenticationError("auth failed"), 4),
        (ProviderError("provider failed"), 4),
        (SyncError("sync failed"), 5),
        (RuntimeError("boom"), 1),
    ],
)
def test_main_maps_errors_to_exit_codes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
    exit_code: int,
) -> None:
    def _raise(_: object) -> None:
        raise error

    monkeypatch.setattr("planpilot.cli.asyncio.run", _raise)

    actual = main(["sync", "--config", "planpilot.json", "--dry-run"])

    assert actual == exit_code
    captured = capsys.readouterr()
    assert "error:" in captured.err
    assert str(error) in captured.err


def test_format_summary_apply_mode_shows_existing_counts(tmp_path: Path) -> None:
    result, config = _make_sync_result(dry_run=False, sync_path=tmp_path / "sync-map.json")

    output = _format_summary(result, config)

    assert "planpilot - sync complete (apply)" in output
    assert "Plan ID:   a1b2c3d4e5f6" in output
    assert "Target:    owner/repo" in output
    assert "Board:     https://github.com/orgs/owner/projects/1" in output
    assert "Created:   1 epic(s), 0 story(s), 0 task(s)" in output
    assert "Existing:  0 epic(s), 1 story(s), 1 task(s)" in output
    assert "Epic   E1" in output
    assert "Story  S1" in output
    assert "Task   T1" in output
    assert "Sync map:  " in output
    assert str(config.sync_path) in output


def test_format_summary_dry_run_mode_uses_dry_run_sync_map_path(tmp_path: Path) -> None:
    result, config = _make_sync_result(dry_run=True, sync_path=tmp_path / "sync-map.json")

    output = _format_summary(result, config)

    assert "planpilot - sync complete (dry-run)" in output
    assert f"Sync map:  {config.sync_path}.dry-run" in output
    assert "[dry-run] No changes were made" in output
