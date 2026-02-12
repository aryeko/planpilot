from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from planpilot import AuthenticationError, ConfigError, MapSyncResult, SyncError, SyncMap
from planpilot.cli import (
    _format_map_sync_summary,
    _package_version,
    _resolve_selected_plan_id,
    _run_map_sync,
    _validate_board_url,
    build_parser,
    main,
)


def _make_map_result(*, dry_run: bool) -> MapSyncResult:
    return MapSyncResult(
        sync_map=SyncMap(
            plan_id="abc123",
            target="owner/repo",
            board_url="https://github.com/orgs/owner/projects/1",
            entries={"E1": {"id": "1", "key": "#1", "url": "https://github.com/owner/repo/issues/1"}},
        ),
        added=["E1"],
        updated=["S1"],
        removed=["T9"],
        candidate_plan_ids=["abc123", "zzz999"],
        dry_run=dry_run,
    )


def test_build_parser_map_sync_accepts_arguments() -> None:
    parser = build_parser()

    args = parser.parse_args(["map", "sync", "--config", "planpilot.json", "--dry-run", "--plan-id", "abc123"])

    assert args.command == "map"
    assert args.map_command == "sync"
    assert args.config == "planpilot.json"
    assert args.plan_id == "abc123"
    assert args.dry_run is True


def test_build_parser_map_sync_defaults_config_path() -> None:
    parser = build_parser()

    args = parser.parse_args(["map", "sync", "--dry-run"])

    assert args.config == "./planpilot.json"


def test_resolve_selected_plan_id_prefers_explicit_value() -> None:
    selected = _resolve_selected_plan_id(explicit_plan_id="abc123", candidate_plan_ids=["x", "y"])
    assert selected == "abc123"


def test_resolve_selected_plan_id_requires_candidates_without_explicit() -> None:
    with pytest.raises(ConfigError, match="No remote PLAN_ID"):
        _resolve_selected_plan_id(explicit_plan_id=None, candidate_plan_ids=[])


def test_resolve_selected_plan_id_non_interactive_requires_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)

    with pytest.raises(ConfigError, match="Multiple remote PLAN_ID"):
        _resolve_selected_plan_id(explicit_plan_id=None, candidate_plan_ids=["a", "b"])


def test_resolve_selected_plan_id_interactive_prompts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    fake_q = SimpleNamespace(select=lambda *args, **kwargs: SimpleNamespace(ask=lambda: "b"))
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    selected = _resolve_selected_plan_id(explicit_plan_id=None, candidate_plan_ids=["a", "b"])

    assert selected == "b"


@pytest.mark.asyncio
async def test_run_map_sync_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = SimpleNamespace(sync_path=tmp_path / "sync-map.json")
    expected = _make_map_result(dry_run=True)

    class _FakeSDK:
        async def discover_remote_plan_ids(self) -> list[str]:
            return ["abc123"]

        async def map_sync(self, *, plan_id: str, dry_run: bool) -> MapSyncResult:
            assert plan_id == "abc123"
            assert dry_run is True
            return expected

    from_config_calls: list[set[str]] = []

    async def _fake_from_config(_config: object, **kwargs: object) -> _FakeSDK:
        from_config_calls.append(set(kwargs))
        assert set(kwargs) == {"progress"}
        return _FakeSDK()

    monkeypatch.setattr("planpilot.cli.load_config", lambda _path: config)
    monkeypatch.setattr("planpilot.cli.PlanPilot.from_config", _fake_from_config)

    args = argparse.Namespace(
        command="map",
        map_command="sync",
        config="planpilot.json",
        plan_id=None,
        dry_run=True,
        apply=False,
        verbose=False,
    )

    actual = await _run_map_sync(args)

    assert actual.sync_map.plan_id == "abc123"
    assert actual.candidate_plan_ids == ["abc123"]
    assert len(from_config_calls) == 2


@pytest.mark.asyncio
async def test_run_map_sync_respects_explicit_plan_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = SimpleNamespace(sync_path=tmp_path / "sync-map.json")
    expected = _make_map_result(dry_run=False)

    class _FakeSDK:
        async def discover_remote_plan_ids(self) -> list[str]:
            return ["abc123", "zzz999"]

        async def map_sync(self, *, plan_id: str, dry_run: bool) -> MapSyncResult:
            assert plan_id == "manual-id"
            assert dry_run is False
            return expected

    from_config_calls: list[set[str]] = []

    async def _fake_from_config(_config: object, **kwargs: object) -> _FakeSDK:
        from_config_calls.append(set(kwargs))
        assert set(kwargs) == {"progress"}
        return _FakeSDK()

    monkeypatch.setattr("planpilot.cli.load_config", lambda _path: config)
    monkeypatch.setattr("planpilot.cli.PlanPilot.from_config", _fake_from_config)

    args = argparse.Namespace(
        command="map",
        map_command="sync",
        config="planpilot.json",
        plan_id="manual-id",
        dry_run=False,
        apply=True,
        verbose=False,
    )

    actual = await _run_map_sync(args)

    assert actual.sync_map.plan_id == "abc123"
    assert actual.candidate_plan_ids == ["abc123", "zzz999"]
    assert len(from_config_calls) == 2


@pytest.mark.asyncio
async def test_run_map_sync_verbose_skips_progress(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = SimpleNamespace(sync_path=tmp_path / "sync-map.json")
    expected = _make_map_result(dry_run=True)

    class _FakeSDK:
        async def discover_remote_plan_ids(self) -> list[str]:
            return ["abc123"]

        async def map_sync(self, *, plan_id: str, dry_run: bool) -> MapSyncResult:
            assert plan_id == "abc123"
            assert dry_run is True
            return expected

    async def _fake_from_config(_config: object, **kwargs: object) -> _FakeSDK:
        assert kwargs == {}
        return _FakeSDK()

    monkeypatch.setattr("planpilot.cli.load_config", lambda _path: config)
    monkeypatch.setattr("planpilot.cli.PlanPilot.from_config", _fake_from_config)

    args = argparse.Namespace(
        command="map",
        map_command="sync",
        config="planpilot.json",
        plan_id=None,
        dry_run=True,
        apply=False,
        verbose=True,
    )

    actual = await _run_map_sync(args)

    assert actual.sync_map.plan_id == "abc123"


def test_format_map_sync_summary_includes_counts_and_notice(tmp_path: Path) -> None:
    result = _make_map_result(dry_run=True)
    config = SimpleNamespace(sync_path=tmp_path / "sync-map.json")

    output = _format_map_sync_summary(result, config)

    assert "planpilot - map sync complete (dry-run)" in output
    assert "Candidates:   2 discovered" in output
    assert "Added:        1 (E1)" in output
    assert "Updated:      1 (S1)" in output
    assert "Removed:      1 (T9)" in output
    assert "[dry-run] No changes were made" in output


def test_format_map_sync_summary_apply_mode_handles_empty_id_lists(tmp_path: Path) -> None:
    result = MapSyncResult(
        sync_map=SyncMap(
            plan_id="abc123",
            target="owner/repo",
            board_url="https://github.com/orgs/owner/projects/1",
            entries={},
        ),
        added=[],
        updated=[],
        removed=[],
        candidate_plan_ids=[],
        dry_run=False,
    )
    config = SimpleNamespace(sync_path=tmp_path / "sync-map.json")

    output = _format_map_sync_summary(result, config)

    assert "planpilot - map sync complete (apply)" in output
    assert "Added:        0 (none)" in output
    assert "Updated:      0 (none)" in output
    assert "Removed:      0 (none)" in output
    assert "[dry-run] No changes were made" not in output


def test_main_routes_to_map_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("planpilot.cli.asyncio.run", lambda _coroutine: None)

    exit_code = main(["map", "sync", "--config", "planpilot.json", "--dry-run", "--plan-id", "abc123"])

    assert exit_code == 0


def test_main_map_sync_enables_verbose_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("planpilot.cli.asyncio.run", lambda _coroutine: None)

    captured: dict[str, object] = {}

    def _fake_basic_config(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr("planpilot.cli.logging.basicConfig", _fake_basic_config)

    exit_code = main(["map", "sync", "--config", "planpilot.json", "--dry-run", "--verbose"])

    assert exit_code == 0
    assert captured["level"] == 10
    assert captured["stream"] is sys.stderr


def test_validate_board_url_helper_accepts_and_rejects_values() -> None:
    assert _validate_board_url("https://github.com/orgs/acme/projects/1") is True
    assert _validate_board_url("https://github.com/orgs/acme/projects/") is not True
    assert _validate_board_url("  ") == "Board URL is required"


def test_package_version_handles_missing_distribution(monkeypatch: pytest.MonkeyPatch) -> None:
    class _PkgNotFound(Exception):
        pass

    monkeypatch.setattr("planpilot.cli.version", lambda _name: (_ for _ in ()).throw(_PkgNotFound()))
    monkeypatch.setattr("planpilot.cli.PackageNotFoundError", _PkgNotFound)

    assert _package_version() == "0.0.0"


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (ConfigError("bad"), 3),
        (AuthenticationError("auth"), 4),
        (SyncError("sync"), 5),
        (RuntimeError("boom"), 1),
    ],
)
def test_main_map_sync_error_mapping(monkeypatch: pytest.MonkeyPatch, error: Exception, expected_code: int) -> None:
    def _raise(_coroutine: object) -> None:
        raise error

    monkeypatch.setattr("planpilot.cli.asyncio.run", _raise)

    exit_code = main(["map", "sync", "--config", "planpilot.json", "--dry-run", "--plan-id", "abc123"])

    assert exit_code == expected_code


def test_main_map_unsupported_subcommand_returns_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class _FakeParser:
        def parse_args(self, _argv: list[str] | None) -> argparse.Namespace:
            return argparse.Namespace(command="map", map_command="noop", verbose=False)

    monkeypatch.setattr("planpilot.cli.build_parser", lambda: _FakeParser())

    exit_code = main([])

    assert exit_code == 2
    assert "unsupported map command" in capsys.readouterr().err


def test_resolve_selected_plan_id_errors_when_questionary_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.delitem(sys.modules, "questionary", raising=False)
    original_import = __import__

    def _fake_import(name: str, *args: Any, **kwargs: Any):
        if name == "questionary":
            raise ImportError("missing questionary")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _fake_import)
    with pytest.raises(ConfigError, match="questionary is required"):
        _resolve_selected_plan_id(explicit_plan_id=None, candidate_plan_ids=["a", "b"])


def test_resolve_selected_plan_id_errors_on_abort(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    fake_q = SimpleNamespace(select=lambda *args, **kwargs: SimpleNamespace(ask=lambda: None))
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    with pytest.raises(ConfigError, match="Aborted plan-id selection"):
        _resolve_selected_plan_id(explicit_plan_id=None, candidate_plan_ids=["a", "b"])
