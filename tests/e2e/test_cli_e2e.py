from __future__ import annotations

import json
from pathlib import Path

import pytest

from planpilot import AuthenticationError, ConfigError, ProviderError, SyncError
from planpilot.cli import main
from planpilot.providers.dry_run import DryRunProvider

FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "plans"


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
