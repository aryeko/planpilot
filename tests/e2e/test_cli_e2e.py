from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from planpilot import AuthenticationError, ConfigError, ProviderError, SyncError
from planpilot.cli import main
from planpilot.providers.dry_run import DryRunProvider

FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "plans"


@pytest.fixture(autouse=True)
def _mock_init_auth_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("planpilot.cli._resolve_init_token", lambda **_kw: "fake-token")
    monkeypatch.setattr("planpilot.cli._validate_github_auth_for_init", lambda **_kw: "org")


def _write_config(
    tmp_path: Path,
    *,
    provider: str,
    plan_paths: dict[str, str],
    auth: str = "gh-cli",
    token: str | None = None,
) -> Path:
    payload: dict[str, object] = {
        "provider": provider,
        "target": "owner/repo",
        "board_url": "https://github.com/orgs/owner/projects/1",
        "plan_paths": plan_paths,
        "sync_path": str(tmp_path / "sync-map.json"),
        "validation_mode": "strict",
    }
    if auth != "gh-cli":
        payload["auth"] = auth
    if token is not None:
        payload["token"] = token

    config_path = tmp_path / "planpilot.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    return config_path


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_cli_dry_run_happy_path_split_input(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    split_dir = FIXTURES_ROOT / "split"
    config_path = _write_config(
        tmp_path,
        provider="github",
        plan_paths={
            "epics": str(split_dir / "epics.json"),
            "stories": str(split_dir / "stories.json"),
            "tasks": str(split_dir / "tasks.json"),
        },
    )

    exit_code = main(["sync", "--config", str(config_path), "--dry-run"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "planpilot - sync complete (dry-run)" in captured.out
    assert "Created:   1 epic(s), 1 story(s), 1 task(s)" in captured.out
    assert (tmp_path / "sync-map.json").exists() is False
    assert (tmp_path / "sync-map.json.dry-run").exists() is True


def test_cli_apply_happy_path_split_input_with_dry_run_provider(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    split_dir = FIXTURES_ROOT / "split"
    config_path = _write_config(
        tmp_path,
        provider="dry-run",
        auth="token",
        token="offline-token",
        plan_paths={
            "epics": str(split_dir / "epics.json"),
            "stories": str(split_dir / "stories.json"),
            "tasks": str(split_dir / "tasks.json"),
        },
    )

    exit_code = main(["sync", "--config", str(config_path), "--apply"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "planpilot - sync complete (apply)" in captured.out
    assert "Created:   1 epic(s), 1 story(s), 1 task(s)" in captured.out
    assert (tmp_path / "sync-map.json").exists() is True
    assert (tmp_path / "sync-map.json.dry-run").exists() is False


def test_cli_unified_input_happy_path_dry_run_and_apply(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    unified_dir = FIXTURES_ROOT / "unified"
    config_path = _write_config(
        tmp_path,
        provider="dry-run",
        auth="token",
        token="offline-token",
        plan_paths={"unified": str(unified_dir / "plan.json")},
    )

    dry_run_exit = main(["sync", "--config", str(config_path), "--dry-run"])
    dry_run_out = capsys.readouterr()

    assert dry_run_exit == 0
    assert "planpilot - sync complete (dry-run)" in dry_run_out.out
    assert "Created:   1 epic(s), 1 story(s), 1 task(s)" in dry_run_out.out
    assert (tmp_path / "sync-map.json.dry-run").exists() is True

    apply_exit = main(["sync", "--config", str(config_path), "--apply"])
    apply_out = capsys.readouterr()

    assert apply_exit == 0
    assert "planpilot - sync complete (apply)" in apply_out.out
    assert "Created:   1 epic(s), 1 story(s), 1 task(s)" in apply_out.out
    assert (tmp_path / "sync-map.json").exists() is True


def test_cli_apply_rerun_is_idempotent_with_persistent_dry_run_provider(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    split_dir = FIXTURES_ROOT / "split"
    provider = DryRunProvider()
    config_path = _write_config(
        tmp_path,
        provider="dry-run",
        auth="token",
        token="offline-token",
        plan_paths={
            "epics": str(split_dir / "epics.json"),
            "stories": str(split_dir / "stories.json"),
            "tasks": str(split_dir / "tasks.json"),
        },
    )

    monkeypatch.setattr("planpilot.sdk.create_provider", lambda *_args, **_kwargs: provider)

    first_exit = main(["sync", "--config", str(config_path), "--apply"])
    first_out = capsys.readouterr()
    first_map = _load_json(tmp_path / "sync-map.json")

    second_exit = main(["sync", "--config", str(config_path), "--apply"])
    second_out = capsys.readouterr()
    second_map = _load_json(tmp_path / "sync-map.json")

    assert first_exit == 0
    assert second_exit == 0
    assert "Created:   1 epic(s), 1 story(s), 1 task(s)" in first_out.out
    assert "Created:   0 epic(s), 0 story(s), 0 task(s)" in second_out.out
    assert "Existing:  1 epic(s), 1 story(s), 1 task(s)" in second_out.out
    assert first_map["entries"] == second_map["entries"]


def test_cli_apply_update_variant_reuses_mapping_without_duplication(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = DryRunProvider()
    baseline_path = FIXTURES_ROOT / "unified" / "plan.json"
    variant_path = FIXTURES_ROOT / "unified" / "update_variant.json"
    working_plan = tmp_path / "working-plan.json"

    working_plan.write_text(baseline_path.read_text(encoding="utf-8"), encoding="utf-8")
    config_path = _write_config(
        tmp_path,
        provider="dry-run",
        auth="token",
        token="offline-token",
        plan_paths={"unified": str(working_plan)},
    )

    monkeypatch.setattr("planpilot.sdk.create_provider", lambda *_args, **_kwargs: provider)
    monkeypatch.setattr("planpilot.sdk.PlanHasher.compute_plan_id", lambda *_args, **_kwargs: "stable-plan-1")

    first_exit = main(["sync", "--config", str(config_path), "--apply"])
    _ = capsys.readouterr()
    first_map = _load_json(tmp_path / "sync-map.json")

    working_plan.write_text(variant_path.read_text(encoding="utf-8"), encoding="utf-8")

    second_exit = main(["sync", "--config", str(config_path), "--apply"])
    second_out = capsys.readouterr()
    second_map = _load_json(tmp_path / "sync-map.json")

    assert first_exit == 0
    assert second_exit == 0
    assert "Created:   0 epic(s), 0 story(s), 0 task(s)" in second_out.out
    assert "Existing:  1 epic(s), 1 story(s), 1 task(s)" in second_out.out
    assert first_map["entries"] == second_map["entries"]
    assert any(
        operation.name == "update_item" and operation.payload.get("title") == "Offline unified story UPDATED"
        for operation in provider.operations
    )


@pytest.mark.parametrize(
    ("fixture_name", "error_fragment"),
    [
        ("strict_missing_parent.json", "missing parent reference"),
        ("strict_missing_dependency.json", "missing dependency reference"),
    ],
)
def test_cli_strict_validation_failure_exits_3(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fixture_name: str, error_fragment: str
) -> None:
    invalid_path = FIXTURES_ROOT / "invalid" / fixture_name
    config_path = _write_config(
        tmp_path,
        provider="dry-run",
        auth="token",
        token="offline-token",
        plan_paths={"unified": str(invalid_path)},
    )

    exit_code = main(["sync", "--config", str(config_path), "--apply"])

    assert exit_code == 3
    captured = capsys.readouterr()
    assert "error:" in captured.err
    assert error_fragment in captured.err


def test_cli_usage_failure_exits_2() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["sync", "--config", "planpilot.json"])

    assert exc.value.code == 2


def test_cli_apply_with_dry_run_provider_records_pipeline_operations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    split_dir = FIXTURES_ROOT / "split"
    provider = DryRunProvider()
    config_path = _write_config(
        tmp_path,
        provider="dry-run",
        auth="token",
        token="offline-token",
        plan_paths={
            "epics": str(split_dir / "epics.json"),
            "stories": str(split_dir / "stories.json"),
            "tasks": str(split_dir / "tasks.json"),
        },
    )

    monkeypatch.setattr("planpilot.sdk.create_provider", lambda *_args, **_kwargs: provider)

    exit_code = main(["sync", "--config", str(config_path), "--apply"])

    assert exit_code == 0
    names = [operation.name for operation in provider.operations]
    assert names[0] == "search_items"
    assert names.count("create_item") == 3
    assert names.count("update_item") == 3
    assert names.count("set_parent") == 2
    create_sequences = [operation.sequence for operation in provider.operations if operation.name == "create_item"]
    update_sequences = [operation.sequence for operation in provider.operations if operation.name == "update_item"]
    relation_sequences = [
        operation.sequence for operation in provider.operations if operation.name in {"set_parent", "add_dependency"}
    ]
    assert max(create_sequences) < min(update_sequences)
    assert max(update_sequences) < min(relation_sequences)


def test_cli_summary_contract_apply_output_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    split_dir = FIXTURES_ROOT / "split"
    provider = DryRunProvider()
    config_path = _write_config(
        tmp_path,
        provider="dry-run",
        auth="token",
        token="offline-token",
        plan_paths={
            "epics": str(split_dir / "epics.json"),
            "stories": str(split_dir / "stories.json"),
            "tasks": str(split_dir / "tasks.json"),
        },
    )
    monkeypatch.setattr("planpilot.sdk.create_provider", lambda *_args, **_kwargs: provider)

    exit_code = main(["sync", "--config", str(config_path), "--apply"])

    assert exit_code == 0
    output = capsys.readouterr().out
    header_index = output.index("planpilot - sync complete (apply)")
    plan_index = output.index("Plan ID:")
    created_index = output.index("Created:")
    epic_index = output.index("Epic")
    story_index = output.index("Story")
    task_index = output.index("Task")
    sync_map_index = output.index("Sync map:")

    assert header_index < plan_index < created_index < epic_index < story_index < task_index < sync_map_index


def test_cli_sync_map_contract_for_dry_run_and_apply(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    split_dir = FIXTURES_ROOT / "split"
    provider = DryRunProvider()
    config_path = _write_config(
        tmp_path,
        provider="dry-run",
        auth="token",
        token="offline-token",
        plan_paths={
            "epics": str(split_dir / "epics.json"),
            "stories": str(split_dir / "stories.json"),
            "tasks": str(split_dir / "tasks.json"),
        },
    )
    monkeypatch.setattr("planpilot.sdk.create_provider", lambda *_args, **_kwargs: provider)

    dry_run_exit = main(["sync", "--config", str(config_path), "--dry-run"])
    _ = capsys.readouterr()
    apply_exit = main(["sync", "--config", str(config_path), "--apply"])
    _ = capsys.readouterr()

    assert dry_run_exit == 0
    assert apply_exit == 0

    dry_run_path = tmp_path / "sync-map.json.dry-run"
    apply_path = tmp_path / "sync-map.json"
    assert dry_run_path.exists()
    assert apply_path.exists()

    for path in (dry_run_path, apply_path):
        payload = _load_json(path)
        assert set(payload) == {"plan_id", "target", "board_url", "entries"}
        entries = payload["entries"]
        assert isinstance(entries, dict)
        assert set(entries.keys()) == {"E1", "S1", "T1"}
        for item in entries.values():
            assert isinstance(item, dict)
            assert {"id", "key", "url", "item_type"}.issubset(item.keys())
            assert str(item["id"]).startswith("dry-run-")
            assert item["key"] == "dry-run"
            assert item["url"] == "dry-run"


@pytest.mark.parametrize(
    ("error", "expected_exit_code"),
    [
        (ConfigError("invalid config"), 3),
        (AuthenticationError("auth failure"), 4),
        (ProviderError("provider failure"), 4),
        (SyncError("sync failure"), 5),
        (RuntimeError("unexpected failure"), 1),
    ],
)
def test_cli_exit_code_mappings_in_process(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
    expected_exit_code: int,
) -> None:
    def _raise(_: object) -> None:
        raise error

    monkeypatch.setattr("planpilot.cli.asyncio.run", _raise)

    exit_code = main(["sync", "--config", "planpilot.json", "--dry-run"])

    assert exit_code == expected_exit_code
    captured = capsys.readouterr()
    assert "error:" in captured.err
    assert str(error) in captured.err


# ---------------------------------------------------------------------------
# map sync subcommand E2E tests
# ---------------------------------------------------------------------------


def test_cli_map_sync_apply_reconciles_local_sync_map(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    split_dir = FIXTURES_ROOT / "split"
    working_split = tmp_path / "working-split"
    working_split.mkdir(parents=True, exist_ok=True)
    shutil.copy(split_dir / "epics.json", working_split / "epics.json")
    shutil.copy(split_dir / "stories.json", working_split / "stories.json")
    shutil.copy(split_dir / "tasks.json", working_split / "tasks.json")
    provider = DryRunProvider()
    config_path = _write_config(
        tmp_path,
        provider="dry-run",
        auth="token",
        token="offline-token",
        plan_paths={
            "epics": str(working_split / "epics.json"),
            "stories": str(working_split / "stories.json"),
            "tasks": str(working_split / "tasks.json"),
        },
    )
    monkeypatch.setattr("planpilot.sdk.create_provider", lambda *_args, **_kwargs: provider)

    sync_exit = main(["sync", "--config", str(config_path), "--apply"])
    _ = capsys.readouterr()
    assert sync_exit == 0

    sync_map_path = tmp_path / "sync-map.json"
    original_map = _load_json(sync_map_path)
    entries = original_map["entries"]
    assert isinstance(entries, dict)
    plan_id = str(original_map["plan_id"])
    entries.pop("S1", None)
    entries["STALE"] = {"id": "stale", "key": "#999", "url": "https://stale.example", "item_type": "TASK"}
    sync_map_path.write_text(json.dumps(original_map), encoding="utf-8")

    map_exit = main(["map", "sync", "--config", str(config_path), "--apply", "--plan-id", plan_id])
    captured = capsys.readouterr()

    assert map_exit == 0
    assert "planpilot - map sync complete (apply)" in captured.out
    assert "Added:        1 (S1)" in captured.out
    assert "Removed:      1 (STALE)" in captured.out

    reconciled = _load_json(sync_map_path)
    reconciled_entries = reconciled["entries"]
    assert isinstance(reconciled_entries, dict)
    assert sorted(reconciled_entries.keys()) == ["E1", "S1", "T1"]


# ---------------------------------------------------------------------------
# planpilot init — e2e tests
# ---------------------------------------------------------------------------


class _FakeQuestion:
    """Mimics questionary.Question — returns a canned value from .ask()."""

    def __init__(self, value: Any) -> None:
        self._value = value

    def ask(self) -> Any:
        return self._value


def _build_fake_questionary(answers: dict[str, Any]) -> SimpleNamespace:
    """Build a fake questionary module that resolves prompts by keyword match."""

    def _find(prompt: str) -> Any:
        for key, value in answers.items():
            if key.lower() in prompt.lower():
                return value
        raise KeyError(f"no answer configured for prompt: {prompt!r}")  # pragma: no cover

    return SimpleNamespace(
        select=lambda prompt, **kw: _FakeQuestion(_find(prompt)),
        text=lambda prompt, **kw: _FakeQuestion(_find(prompt)),
        confirm=lambda prompt, **kw: _FakeQuestion(_find(prompt)),
        password=lambda prompt, **kw: _FakeQuestion(_find(prompt)),
        Choice=lambda label, value: value,
    )


# -- defaults mode -----------------------------------------------------------


def test_e2e_init_defaults_generates_valid_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``planpilot init --defaults`` creates a parseable config file."""
    output = tmp_path / "planpilot.json"
    monkeypatch.setattr("planpilot.cli.detect_target", lambda: "e2e-org/e2e-repo")
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)

    exit_code = main(["init", "--defaults", "--output", str(output)])

    assert exit_code == 0
    assert output.exists()
    config = json.loads(output.read_text())
    assert config["provider"] == "github"
    assert config["target"] == "e2e-org/e2e-repo"
    assert "plan_paths" in config
    captured = capsys.readouterr()
    assert "Config written to" in captured.out


def test_e2e_init_defaults_refuses_overwrite(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "planpilot.json"
    output.write_text("{}")

    exit_code = main(["init", "--defaults", "--output", str(output)])

    assert exit_code == 2
    assert "already exists" in capsys.readouterr().err


def test_e2e_init_defaults_then_dry_run_sync(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Generate config via ``init --defaults``, patch plan_paths to real
    fixtures, then run ``sync --dry-run`` — full pipeline round-trip."""
    split_dir = FIXTURES_ROOT / "split"
    config_path = tmp_path / "planpilot.json"

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: "owner/repo")
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)

    # Step 1: generate config
    init_exit = main(["init", "--defaults", "--output", str(config_path)])
    _ = capsys.readouterr()
    assert init_exit == 0

    # Step 2: patch plan_paths and board_url to point to real fixtures
    config = json.loads(config_path.read_text())
    config["plan_paths"] = {
        "epics": str(split_dir / "epics.json"),
        "stories": str(split_dir / "stories.json"),
        "tasks": str(split_dir / "tasks.json"),
    }
    config["board_url"] = "https://github.com/orgs/owner/projects/1"
    config["sync_path"] = str(tmp_path / "sync-map.json")
    config_path.write_text(json.dumps(config))

    # Step 3: dry-run sync with the generated config
    sync_exit = main(["sync", "--config", str(config_path), "--dry-run"])

    assert sync_exit == 0
    captured = capsys.readouterr()
    assert "planpilot - sync complete (dry-run)" in captured.out
    assert "Created:" in captured.out
    assert (tmp_path / "sync-map.json.dry-run").exists()


# -- interactive mode ---------------------------------------------------------


def test_e2e_init_interactive_split_generates_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Interactive wizard (split layout) produces a valid config and stubs."""
    output = tmp_path / "planpilot.json"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)

    fake_q = _build_fake_questionary(
        {
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
            "Discovery label": "planpilot",
            "Configure field defaults": False,
            "Create empty": True,
        }
    )
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    exit_code = main(["init", "--output", str(output)])

    assert exit_code == 0
    config = json.loads(output.read_text())
    assert config["target"] == "org/repo"
    assert config["plan_paths"]["epics"] == ".plans/epics.json"
    # Verify stubs were created
    assert (tmp_path / ".plans" / "epics.json").exists()
    assert (tmp_path / ".plans" / "stories.json").exists()
    assert (tmp_path / ".plans" / "tasks.json").exists()
    captured = capsys.readouterr()
    assert "Next steps:" in captured.out


def test_e2e_init_interactive_unified_generates_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Interactive wizard (unified layout) produces a valid config."""
    output = tmp_path / "planpilot.json"
    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)

    fake_q = _build_fake_questionary(
        {
            "Provider": "github",
            "Target repository": "org/repo",
            "Board URL": "https://github.com/orgs/org/projects/1",
            "Plan file layout": "unified",
            "Unified plan": ".plans/plan.json",
            "Sync map": ".plans/sync-map.json",
            "Authentication": "gh-cli",
            "Configure advanced": False,
            "Discovery label": "planpilot",
            "Configure field defaults": False,
            "Create empty": False,
        }
    )
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    exit_code = main(["init", "--output", str(output)])

    assert exit_code == 0
    config = json.loads(output.read_text())
    assert config["plan_paths"] == {"unified": ".plans/plan.json"}


def test_e2e_init_interactive_then_dry_run_sync(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Full round-trip: interactive init -> sync --dry-run.

    The wizard creates a config pointing to real fixture plan files,
    then sync uses that config to produce a valid dry-run output.
    """
    split_dir = FIXTURES_ROOT / "split"
    config_path = tmp_path / "planpilot.json"

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)

    fake_q = _build_fake_questionary(
        {
            "Provider": "github",
            "Target repository": "owner/repo",
            "Board URL": "https://github.com/orgs/owner/projects/1",
            "Plan file layout": "split",
            "Epics file": str(split_dir / "epics.json"),
            "Stories file": str(split_dir / "stories.json"),
            "Tasks file": str(split_dir / "tasks.json"),
            "Sync map": str(tmp_path / "sync-map.json"),
            "Authentication": "gh-cli",
            "Configure advanced": False,
            "Discovery label": "planpilot",
            "Configure field defaults": False,
            "Create empty": False,
        }
    )
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    # Step 1: interactive init
    init_exit = main(["init", "--output", str(config_path)])
    _ = capsys.readouterr()
    assert init_exit == 0
    assert config_path.exists()

    # Step 2: dry-run sync with the generated config
    sync_exit = main(["sync", "--config", str(config_path), "--dry-run"])

    assert sync_exit == 0
    captured = capsys.readouterr()
    assert "planpilot - sync complete (dry-run)" in captured.out
    assert "Created:" in captured.out


def test_e2e_init_interactive_with_advanced_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Interactive wizard with advanced options enabled."""
    output = tmp_path / "planpilot.json"
    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)

    fake_q = _build_fake_questionary(
        {
            "Provider": "github",
            "Target repository": "org/repo",
            "Board URL": "https://github.com/orgs/org/projects/1",
            "Plan file layout": "split",
            "Epics file": ".plans/epics.json",
            "Stories file": ".plans/stories.json",
            "Tasks file": ".plans/tasks.json",
            "Sync map": ".plans/sync-map.json",
            "Authentication": "env",
            "Configure advanced": True,
            "Validation mode": "partial",
            "Max concurrent": "5",
            "Discovery label": "planpilot",
            "Configure field defaults": False,
            "Create empty": False,
        }
    )
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    exit_code = main(["init", "--output", str(output)])

    assert exit_code == 0
    config = json.loads(output.read_text())
    assert config["auth"] == "env"
    assert config["validation_mode"] == "partial"
    assert config["max_concurrent"] == 5


def test_e2e_init_interactive_with_static_token_auth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "planpilot.json"
    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)

    fake_q = _build_fake_questionary(
        {
            "Provider": "github",
            "Target repository": "org/repo",
            "Board URL": "https://github.com/orgs/org/projects/1",
            "Plan file layout": "unified",
            "Unified plan": ".plans/plan.json",
            "Sync map": ".plans/sync-map.json",
            "Authentication": "token",
            "GitHub token": "ghp_e2e_token",
            "Configure advanced": False,
            "Discovery label": "planpilot",
            "Configure field defaults": False,
            "Create empty": False,
        }
    )
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    exit_code = main(["init", "--output", str(output)])

    assert exit_code == 0
    config = json.loads(output.read_text())
    assert config["auth"] == "token"
    assert config["token"] == "ghp_e2e_token"


def test_e2e_init_interactive_user_board_defaults_label_strategy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "planpilot.json"
    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)

    fake_q = _build_fake_questionary(
        {
            "Provider": "github",
            "Target repository": "org/repo",
            "Board URL": "https://github.com/users/alice/projects/7",
            "Plan file layout": "unified",
            "Unified plan": ".plans/plan.json",
            "Sync map": ".plans/sync-map.json",
            "Authentication": "gh-cli",
            "Configure advanced": False,
            "Discovery label": "planpilot",
            "Configure field defaults": False,
            "Create empty": False,
        }
    )
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    exit_code = main(["init", "--output", str(output)])

    assert exit_code == 0
    config = json.loads(output.read_text())
    assert config["field_config"]["create_type_strategy"] == "label"


def test_e2e_init_interactive_ctrl_c_aborts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Ctrl+C during the wizard returns exit code 2."""
    output = tmp_path / "planpilot.json"
    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)

    # Return None from first prompt to simulate Ctrl+C
    fake_q = _build_fake_questionary({"Provider": None})
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    exit_code = main(["init", "--output", str(output)])

    assert exit_code == 2
    assert not output.exists()
    assert "Aborted" in capsys.readouterr().out


def test_e2e_init_interactive_overwrite_declined(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """User declines overwrite of existing file."""
    output = tmp_path / "planpilot.json"
    output.write_text('{"original": true}')

    fake_q = _build_fake_questionary({"already exists": False})
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    exit_code = main(["init", "--output", str(output)])

    assert exit_code == 2
    # Original file is preserved
    assert json.loads(output.read_text()) == {"original": True}


def test_e2e_init_interactive_overwrite_accepted_then_sync(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """User accepts overwrite, new config works for sync."""
    split_dir = FIXTURES_ROOT / "split"
    config_path = tmp_path / "planpilot.json"
    config_path.write_text('{"stale": true}')

    monkeypatch.setattr("planpilot.cli.detect_target", lambda: None)
    monkeypatch.setattr("planpilot.cli.detect_plan_paths", lambda: None)

    fake_q = _build_fake_questionary(
        {
            "already exists": True,
            "Provider": "github",
            "Target repository": "owner/repo",
            "Board URL": "https://github.com/orgs/owner/projects/1",
            "Plan file layout": "split",
            "Epics file": str(split_dir / "epics.json"),
            "Stories file": str(split_dir / "stories.json"),
            "Tasks file": str(split_dir / "tasks.json"),
            "Sync map": str(tmp_path / "sync-map.json"),
            "Authentication": "gh-cli",
            "Configure advanced": False,
            "Discovery label": "planpilot",
            "Configure field defaults": False,
            "Create empty": False,
        }
    )
    monkeypatch.setitem(sys.modules, "questionary", fake_q)

    # Step 1: overwrite existing config
    init_exit = main(["init", "--output", str(config_path)])
    _ = capsys.readouterr()
    assert init_exit == 0
    config = json.loads(config_path.read_text())
    assert "stale" not in config

    # Step 2: sync with the new config
    sync_exit = main(["sync", "--config", str(config_path), "--dry-run"])

    assert sync_exit == 0
    captured = capsys.readouterr()
    assert "planpilot - sync complete (dry-run)" in captured.out
