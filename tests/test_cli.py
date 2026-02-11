from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from planpilot import (
    AuthenticationError,
    CleanResult,
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
from planpilot.cli import _format_clean_summary, _format_summary, _run_clean, _run_init, _run_sync, build_parser, main
from planpilot.contracts.config import PlanPaths


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


def test_build_parser_requires_subcommand() -> None:
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

    async def _fake_from_config(input_config: PlanPilotConfig, **_kwargs: object):
        assert input_config == config
        return _FakeSDK()

    monkeypatch.setattr("planpilot.cli.load_config", lambda _: config)
    monkeypatch.setattr("planpilot.cli.PlanPilot.from_config", _fake_from_config)

    actual = await _run_sync(args)

    assert actual == result


@pytest.mark.asyncio
async def test_run_sync_verbose_skips_progress(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args = _make_args(dry_run=True)
    args.verbose = True
    config = _make_config(tmp_path)
    result, _ = _make_sync_result(dry_run=True, sync_path=config.sync_path)

    class _FakeSDK:
        async def sync(self, *, dry_run: bool) -> SyncResult:
            return result

    async def _fake_from_config(input_config: PlanPilotConfig, **_kwargs: object):
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
    assert "Items:     3 total (1 epic, 1 story, 1 task)" in output
    assert "Created:   1 (1 epic)" in output
    assert "Matched:   2 (1 story, 1 task)" in output
    assert "Sync map:  " in output
    assert str(config.sync_path) in output


def test_format_summary_dry_run_mode_uses_dry_run_sync_map_path(tmp_path: Path) -> None:
    result, config = _make_sync_result(dry_run=True, sync_path=tmp_path / "sync-map.json")

    output = _format_summary(result, config)

    assert "planpilot - sync complete (dry-run)" in output
    assert f"Sync map:  {config.sync_path}.dry-run" in output
    assert "[dry-run] No changes were made" in output


# ---------------------------------------------------------------------------
# init subcommand
# ---------------------------------------------------------------------------


def test_build_parser_init_accepts_defaults_and_output() -> None:
    parser = build_parser()

    args = parser.parse_args(["init", "--output", "custom.json", "--defaults"])

    assert args.command == "init"
    assert args.output == "custom.json"
    assert args.defaults is True


def test_build_parser_init_defaults_are_sensible() -> None:
    parser = build_parser()

    args = parser.parse_args(["init"])

    assert args.command == "init"
    assert args.output == "planpilot.json"
    assert args.defaults is False


def test_main_routes_to_init(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "planpilot.json"

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: "owner/repo")
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)

    exit_code = main(["init", "--defaults", "--output", str(output)])

    assert exit_code == 0
    assert output.exists()


def test_init_defaults_writes_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "planpilot.json"

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: "myorg/myrepo")
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)

    import json

    args = argparse.Namespace(command="init", output=str(output), defaults=True)
    exit_code = _run_init(args)

    assert exit_code == 0
    config = json.loads(output.read_text())
    assert config["target"] == "myorg/myrepo"
    assert config["provider"] == "github"
    assert "plan_paths" in config


def test_init_defaults_no_git_uses_placeholder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "planpilot.json"

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)

    import json

    args = argparse.Namespace(command="init", output=str(output), defaults=True)
    exit_code = _run_init(args)

    assert exit_code == 0
    config = json.loads(output.read_text())
    assert config["target"] == "owner/repo"


def test_init_defaults_refuses_overwrite(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "planpilot.json"
    output.write_text("{}")

    args = argparse.Namespace(command="init", output=str(output), defaults=True)
    exit_code = _run_init(args)

    assert exit_code == 2
    assert "already exists" in capsys.readouterr().err


def test_init_defaults_uses_detected_plan_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "planpilot.json"

    detected = PlanPaths(epics=Path("plans/e.json"), stories=Path("plans/s.json"), tasks=Path("plans/t.json"))
    monkeypatch.setattr("planpilot.cli.detect_target", lambda: "org/repo")
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: detected)

    args = argparse.Namespace(command="init", output=str(output), defaults=True)
    exit_code = _run_init(args)

    assert exit_code == 0
    config = json.loads(output.read_text())
    assert config["plan_paths"]["epics"] == "plans/e.json"


def test_init_defaults_config_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "planpilot.json"

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: "org/repo")
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)
    monkeypatch.setattr("planpilot.cli.scaffold_config", lambda **kw: (_ for _ in ()).throw(ConfigError("boom")))

    args = argparse.Namespace(command="init", output=str(output), defaults=True)
    exit_code = _run_init(args)

    assert exit_code == 3
    assert "boom" in capsys.readouterr().err


def test_init_defaults_prints_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "planpilot.json"

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: "org/repo")
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)

    args = argparse.Namespace(command="init", output=str(output), defaults=True)
    _run_init(args)

    captured = capsys.readouterr().out
    assert "Config written to" in captured
    assert "planpilot sync --config" in captured


def test_format_summary_no_existing_items(tmp_path: Path) -> None:
    """When all items are newly created, the 'Existing' line should not appear."""
    config = PlanPilotConfig(
        provider="github",
        target="owner/repo",
        board_url="https://github.com/orgs/owner/projects/1",
        plan_paths={"unified": Path("/tmp/plan.json")},
        sync_path=tmp_path / "sync-map.json",
    )
    sync_map = SyncMap(
        plan_id="abc123",
        target=config.target,
        board_url=config.board_url,
        entries={
            "E1": SyncEntry(
                id="1", key="#1", url="https://github.com/owner/repo/issues/1", item_type=PlanItemType.EPIC
            ),
        },
    )
    result = SyncResult(
        sync_map=sync_map,
        items_created={PlanItemType.EPIC: 1, PlanItemType.STORY: 0, PlanItemType.TASK: 0},
        dry_run=False,
    )

    output = _format_summary(result, config)

    assert "Items:     1 total (1 epic)" in output
    assert "Created:   1 (1 epic)" in output
    assert "Matched:" not in output


# ---------------------------------------------------------------------------
# Interactive init wizard tests (questionary mocked)
# ---------------------------------------------------------------------------


class _FakeQuestion:
    """Mimics questionary.Question — returns a canned value from .ask()."""

    def __init__(self, value: Any) -> None:
        self._value = value

    def ask(self) -> Any:
        return self._value


def _build_fake_questionary(answers: dict[str, Any]) -> SimpleNamespace:
    """Build a fake questionary module from a mapping of prompt-prefix -> answer.

    The fake ``select``/``text``/``confirm`` match the *first keyword* of the
    prompt string against the keys in *answers* (case-insensitive contains).
    ``Choice`` is passed through as a no-op wrapper.
    """

    def _find(prompt: str) -> Any:
        for key, value in answers.items():
            if key.lower() in prompt.lower():
                return value
        raise KeyError(f"no answer configured for prompt: {prompt!r}")

    def _select(prompt: str, **_kw: Any) -> _FakeQuestion:
        return _FakeQuestion(_find(prompt))

    def _text(prompt: str, **_kw: Any) -> _FakeQuestion:
        return _FakeQuestion(_find(prompt))

    def _confirm(prompt: str, **_kw: Any) -> _FakeQuestion:
        return _FakeQuestion(_find(prompt))

    return SimpleNamespace(
        select=_select,
        text=_text,
        confirm=_confirm,
        Choice=lambda label, value: value,  # type: ignore[arg-type]
    )


_SPLIT_ANSWERS: dict[str, Any] = {
    "Provider": "github",
    "Target repository": "org/repo",
    "Board URL": "https://github.com/orgs/org/projects/1",
    "Plan file layout": "split",
    "Epics file": ".plans/epics.json",
    "Stories file": ".plans/stories.json",
    "Tasks file": ".plans/tasks.json",
    "Sync map": ".plans/sync-map.json",
    "Authentication": "gh-cli",
    "Configure advanced": False,
    "Create empty": True,
    "already exists": True,
}

_UNIFIED_ANSWERS: dict[str, Any] = {
    **_SPLIT_ANSWERS,
    "Plan file layout": "unified",
    "Unified plan": ".plans/plan.json",
}


def test_init_interactive_split_layout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "planpilot.json"
    fake_q = _build_fake_questionary(_SPLIT_ANSWERS)

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 0
    assert output.exists()
    config = json.loads(output.read_text())
    assert config["target"] == "org/repo"
    assert config["plan_paths"]["epics"] == ".plans/epics.json"


def test_init_interactive_unified_layout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "planpilot.json"
    fake_q = _build_fake_questionary(_UNIFIED_ANSWERS)

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 0
    config = json.loads(output.read_text())
    assert config["plan_paths"] == {"unified": ".plans/plan.json"}


def test_init_interactive_with_advanced(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "planpilot.json"
    answers = {
        **_SPLIT_ANSWERS,
        "Configure advanced": True,
        "Validation mode": "partial",
        "Max concurrent": "3",
    }
    fake_q = _build_fake_questionary(answers)

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 0
    config = json.loads(output.read_text())
    assert config["validation_mode"] == "partial"
    assert config["max_concurrent"] == 3


def test_init_interactive_creates_stubs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "planpilot.json"
    fake_q = _build_fake_questionary(_SPLIT_ANSWERS)

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    # Stubs are created relative to cwd; use monkeypatch to set cwd to tmp_path
    monkeypatch.chdir(tmp_path)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 0
    assert (tmp_path / ".plans" / "epics.json").exists()
    assert (tmp_path / ".plans" / "stories.json").exists()
    assert (tmp_path / ".plans" / "tasks.json").exists()


def test_init_interactive_skips_stubs_when_declined(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "planpilot.json"
    answers = {**_SPLIT_ANSWERS, "Create empty": False}
    fake_q = _build_fake_questionary(answers)

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)
    monkeypatch.setitem(sys.modules, "questionary", fake_q)
    monkeypatch.chdir(tmp_path)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 0
    assert not (tmp_path / ".plans" / "epics.json").exists()


def test_init_interactive_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "planpilot.json"

    # Return None from the first prompt to simulate Ctrl+C
    answers = {**_SPLIT_ANSWERS, "Provider": None}
    fake_q = _build_fake_questionary(answers)

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 2
    assert "Aborted" in capsys.readouterr().out


def test_init_interactive_config_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "planpilot.json"
    fake_q = _build_fake_questionary(_SPLIT_ANSWERS)

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)
    monkeypatch.setattr("planpilot.cli.scaffold_config", lambda **kw: (_ for _ in ()).throw(ConfigError("bad")))
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 3
    assert "bad" in capsys.readouterr().err


def test_init_interactive_with_detected_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "planpilot.json"
    fake_q = _build_fake_questionary(_SPLIT_ANSWERS)

    detected = PlanPaths(epics=Path("plans/e.json"), stories=Path("plans/s.json"), tasks=Path("plans/t.json"))
    monkeypatch.setattr("planpilot.cli.detect_target", lambda: "detected/repo")
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: detected)
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 0
    assert output.exists()


def test_init_interactive_overwrite_confirm_accepted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "planpilot.json"
    output.write_text("{}")

    fake_q = _build_fake_questionary({**_SPLIT_ANSWERS, "already exists": True})

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 0
    config = json.loads(output.read_text())
    assert config["target"] == "org/repo"


def test_init_interactive_overwrite_confirm_declined(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "planpilot.json"
    output.write_text("{}")

    fake_q = _build_fake_questionary({**_SPLIT_ANSWERS, "already exists": False})

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 2
    assert "Aborted" in capsys.readouterr().out


def test_init_interactive_overwrite_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "planpilot.json"
    output.write_text("{}")

    # Simulate Ctrl+C during the overwrite confirm
    fake_confirm = MagicMock(side_effect=KeyboardInterrupt)

    fake_q = SimpleNamespace(confirm=lambda prompt, **kw: SimpleNamespace(ask=fake_confirm))

    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 2
    assert "Aborted" in capsys.readouterr().out


def test_init_interactive_prints_next_steps(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "planpilot.json"
    answers = {**_SPLIT_ANSWERS, "Create empty": False}
    fake_q = _build_fake_questionary(answers)

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    _run_init(args)

    captured = capsys.readouterr().out
    assert "Next steps:" in captured
    assert "planpilot sync --config" in captured


def test_init_interactive_unified_with_detected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "planpilot.json"
    fake_q = _build_fake_questionary(_UNIFIED_ANSWERS)

    detected = PlanPaths(unified=Path("plans/plan.json"))
    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: detected)
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 0


def test_init_interactive_auth_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "planpilot.json"
    answers = {**_SPLIT_ANSWERS, "Authentication": "env", "Create empty": False}
    fake_q = _build_fake_questionary(answers)

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 0
    config = json.loads(output.read_text())
    assert config["auth"] == "env"


def test_init_interactive_target_ctrl_c(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Ctrl+C on the target prompt (None from .ask())."""
    output = tmp_path / "planpilot.json"
    answers = {**_SPLIT_ANSWERS, "Target repository": None}
    fake_q = _build_fake_questionary(answers)

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 2


def test_init_interactive_board_url_ctrl_c(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "planpilot.json"
    answers = {**_SPLIT_ANSWERS, "Board URL": None}
    fake_q = _build_fake_questionary(answers)

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 2


def test_init_interactive_layout_ctrl_c(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "planpilot.json"
    answers = {**_SPLIT_ANSWERS, "Plan file layout": None}
    fake_q = _build_fake_questionary(answers)

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 2


def test_init_interactive_sync_path_ctrl_c(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "planpilot.json"
    answers = {**_SPLIT_ANSWERS, "Sync map": None}
    fake_q = _build_fake_questionary(answers)

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 2


def test_init_interactive_auth_ctrl_c(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "planpilot.json"
    answers = {**_SPLIT_ANSWERS, "Authentication": None}
    fake_q = _build_fake_questionary(answers)

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 2


def test_init_interactive_advanced_ctrl_c(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "planpilot.json"
    answers = {**_SPLIT_ANSWERS, "Configure advanced": None}
    fake_q = _build_fake_questionary(answers)

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 2


def test_init_interactive_advanced_validation_mode_ctrl_c(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "planpilot.json"
    answers = {**_SPLIT_ANSWERS, "Configure advanced": True, "Validation mode": None}
    fake_q = _build_fake_questionary(answers)

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 2


def test_init_interactive_advanced_max_concurrent_ctrl_c(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "planpilot.json"
    answers = {**_SPLIT_ANSWERS, "Configure advanced": True, "Validation mode": "strict", "Max concurrent": None}
    fake_q = _build_fake_questionary(answers)

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 2


def test_init_interactive_split_paths_ctrl_c(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Ctrl+C during one of the split path prompts."""
    output = tmp_path / "planpilot.json"
    answers = {**_SPLIT_ANSWERS, "Tasks file": None}
    fake_q = _build_fake_questionary(answers)

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 2


def test_init_interactive_unified_path_ctrl_c(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "planpilot.json"
    answers = {**_UNIFIED_ANSWERS, "Unified plan": None}
    fake_q = _build_fake_questionary(answers)

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    args = argparse.Namespace(command="init", output=str(output), defaults=False)
    exit_code = _run_init(args)

    assert exit_code == 2


# ---------------------------------------------------------------------------
# clean subcommand
# ---------------------------------------------------------------------------


def test_build_parser_clean_requires_mode_and_config() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["clean", "--config", "planpilot.json"])

    assert exc.value.code == 2


@pytest.mark.parametrize("mode", ["--dry-run", "--apply"])
def test_build_parser_clean_accepts_required_arguments(mode: str) -> None:
    parser = build_parser()

    args = parser.parse_args(["clean", "--config", "planpilot.json", mode])

    assert args.command == "clean"
    assert args.config == "planpilot.json"
    assert args.verbose is False


def test_format_clean_summary_apply_mode() -> None:
    result = CleanResult(plan_id="a1b2c3d4e5f6", items_deleted=3, dry_run=False)

    output = _format_clean_summary(result)

    assert "planpilot - clean complete (apply)" in output
    assert "Plan ID:    a1b2c3d4e5f6" in output
    assert "Deleted:    3 issues" in output
    assert "[dry-run]" not in output


def test_format_clean_summary_dry_run_mode() -> None:
    result = CleanResult(plan_id="a1b2c3d4e5f6", items_deleted=3, dry_run=True)

    output = _format_clean_summary(result)

    assert "planpilot - clean complete (dry-run)" in output
    assert "Deleted:    3 issues" in output
    assert "[dry-run] No issues were deleted" in output


def test_format_clean_summary_single_item() -> None:
    result = CleanResult(plan_id="xyz789", items_deleted=1, dry_run=False)

    output = _format_clean_summary(result)

    assert "Deleted:    1 issue" in output


def test_format_clean_summary_zero_items() -> None:
    result = CleanResult(plan_id="xyz789", items_deleted=0, dry_run=False)

    output = _format_clean_summary(result)

    assert "Deleted:    0 issues" in output


@pytest.mark.asyncio
async def test_run_clean_delegates_to_sdk(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args = argparse.Namespace(
        command="clean",
        config="/tmp/planpilot.json",
        dry_run=True,
        apply=False,
        verbose=False,
    )
    # no --all flag → getattr fallback to False
    config = _make_config(tmp_path)
    result = CleanResult(plan_id="a1b2c3d4e5f6", items_deleted=2, dry_run=True)

    class _FakeSDK:
        async def clean(self, *, dry_run: bool, all_plans: bool) -> CleanResult:
            assert dry_run is True
            assert all_plans is False
            return result

    async def _fake_from_config(input_config: PlanPilotConfig, **_kwargs: object):
        assert input_config == config
        return _FakeSDK()

    monkeypatch.setattr("planpilot.cli.load_config", lambda _: config)
    monkeypatch.setattr("planpilot.cli.PlanPilot.from_config", _fake_from_config)

    actual = await _run_clean(args)

    assert actual == result


@pytest.mark.asyncio
async def test_run_clean_all_flag_passes_through(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args = argparse.Namespace(
        command="clean",
        config="/tmp/planpilot.json",
        dry_run=False,
        apply=True,
        verbose=False,
    )
    # simulate argparse --all
    setattr(args, "all", True)  # noqa: B010
    config = _make_config(tmp_path)
    result = CleanResult(plan_id="a1b2c3d4e5f6", items_deleted=5, dry_run=False)

    class _FakeSDK:
        async def clean(self, *, dry_run: bool, all_plans: bool) -> CleanResult:
            assert dry_run is False
            assert all_plans is True
            return result

    async def _fake_from_config(input_config: PlanPilotConfig, **_kwargs: object):
        return _FakeSDK()

    monkeypatch.setattr("planpilot.cli.load_config", lambda _: config)
    monkeypatch.setattr("planpilot.cli.PlanPilot.from_config", _fake_from_config)

    actual = await _run_clean(args)

    assert actual == result


def test_build_parser_clean_all_flag() -> None:
    parser = build_parser()

    args = parser.parse_args(["clean", "--config", "planpilot.json", "--apply", "--all"])

    assert args.command == "clean"
    assert args.all is True


def test_build_parser_clean_defaults_all_false() -> None:
    parser = build_parser()

    args = parser.parse_args(["clean", "--config", "planpilot.json", "--apply"])

    assert args.all is False


def test_main_routes_to_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("planpilot.cli.asyncio.run", lambda _: None)

    exit_code = main(["clean", "--config", "planpilot.json", "--dry-run"])

    assert exit_code == 0
