from __future__ import annotations

import json
from pathlib import Path

import pytest

from planpilot.contracts.config import PlanPaths, PlanPilotConfig
from planpilot.contracts.exceptions import ConfigError, SyncError
from planpilot.contracts.item import CreateItemInput
from planpilot.contracts.plan import Plan, PlanItemType
from planpilot.sdk import PlanPilot
from tests.fakes.provider import FakeProvider
from tests.fakes.renderer import FakeRenderer


def _make_config(tmp_path: Path) -> PlanPilotConfig:
    return PlanPilotConfig(
        provider="github",
        target="owner/repo",
        board_url="https://github.com/orgs/owner/projects/1",
        plan_paths=PlanPaths(unified=tmp_path / "plan.json"),
        sync_path=tmp_path / "sync-map.json",
    )


def _make_split_config(tmp_path: Path) -> PlanPilotConfig:
    return PlanPilotConfig(
        provider="github",
        target="owner/repo",
        board_url="https://github.com/orgs/owner/projects/1",
        plan_paths=PlanPaths(
            epics=tmp_path / "epics.json",
            stories=tmp_path / "stories.json",
            tasks=tmp_path / "tasks.json",
        ),
        sync_path=tmp_path / "sync-map.json",
    )


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_plan(config: PlanPilotConfig, plan: Plan) -> None:
    payload = {"items": [item.model_dump(mode="json", exclude_none=True) for item in plan.items]}
    assert config.plan_paths.unified is not None
    config.plan_paths.unified.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.asyncio
async def test_discover_remote_plan_ids_returns_unique_sorted(tmp_path: Path, sample_plan: Plan) -> None:
    provider = FakeProvider()
    config = _make_config(tmp_path)
    _write_plan(config, sample_plan)
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=config)
    first_sync = await sdk.sync(sample_plan)

    await provider.create_item(
        CreateItemInput(
            title="Extra",
            body="PLANPILOT_META_V1\nPLAN_ID:zzz999\nITEM_ID:X1\nEND_PLANPILOT_META\n",
            item_type=PlanItemType.TASK,
            labels=[sdk._config.label],
        )
    )

    plan_ids = await sdk.discover_remote_plan_ids()

    assert plan_ids == [first_sync.sync_map.plan_id, "zzz999"]


@pytest.mark.asyncio
async def test_map_sync_dry_run_reconciles_without_writing(tmp_path: Path, sample_plan: Plan) -> None:
    provider = FakeProvider()
    config = _make_config(tmp_path)
    _write_plan(config, sample_plan)
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=config)
    sync_result = await sdk.sync(sample_plan)
    config.sync_path.unlink()

    result = await sdk.map_sync(plan_id=sync_result.sync_map.plan_id, dry_run=True)

    assert result.dry_run is True
    assert sorted(result.added) == ["E1", "S1", "T1"]
    assert result.updated == []
    assert result.removed == []
    assert config.sync_path.exists() is False


@pytest.mark.asyncio
async def test_map_sync_apply_reconciles_added_updated_removed(tmp_path: Path, sample_plan: Plan) -> None:
    provider = FakeProvider()
    config = _make_config(tmp_path)
    _write_plan(config, sample_plan)
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=config)
    sync_result = await sdk.sync(sample_plan)
    plan_id = sync_result.sync_map.plan_id

    # Tamper local sync map: drop T1 and add stale Z9
    payload = _load_json(config.sync_path)
    entries = payload["entries"]
    assert isinstance(entries, dict)
    entries.pop("T1")
    entries["Z9"] = {"id": "gone", "key": "#999", "url": "https://fake/issues/999", "item_type": "TASK"}
    config.sync_path.write_text(json.dumps(payload), encoding="utf-8")

    # Tamper provider metadata for E1 by changing key/url
    e1_provider_id = sync_result.sync_map.entries["E1"].id
    provider.set_item_identity(e1_provider_id, key="#4242", url="https://fake/issues/4242")

    result = await sdk.map_sync(plan_id=plan_id, dry_run=False)

    assert sorted(result.added) == ["T1"]
    assert sorted(result.removed) == ["Z9"]
    assert sorted(result.updated) == ["E1"]

    persisted = _load_json(config.sync_path)
    persisted_entries = persisted["entries"]
    assert isinstance(persisted_entries, dict)
    assert sorted(persisted_entries.keys()) == ["E1", "S1", "T1"]
    assert persisted_entries["E1"]["key"] == "#4242"
    assert persisted_entries["E1"]["url"] == "https://fake/issues/4242"


@pytest.mark.asyncio
async def test_map_sync_includes_discovered_items_not_in_local_plan(tmp_path: Path, sample_plan: Plan) -> None:
    provider = FakeProvider()
    config = _make_config(tmp_path)
    _write_plan(config, sample_plan)
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=config)
    sync_result = await sdk.sync(sample_plan)
    plan_id = sync_result.sync_map.plan_id

    await provider.create_item(
        CreateItemInput(
            title="External item",
            body=f"PLANPILOT_META_V1\nPLAN_ID:{plan_id}\nITEM_ID:EXTERNAL\nEND_PLANPILOT_META\n",
            item_type=PlanItemType.TASK,
            labels=[sdk._config.label],
        )
    )

    result = await sdk.map_sync(plan_id=plan_id, dry_run=True)

    assert "EXTERNAL" in result.sync_map.entries


@pytest.mark.asyncio
async def test_map_sync_invalid_sync_map_file_raises_config_error(tmp_path: Path, sample_plan: Plan) -> None:
    provider = FakeProvider()
    config = _make_config(tmp_path)
    _write_plan(config, sample_plan)
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=config)
    sync_result = await sdk.sync(sample_plan)
    config.sync_path.write_text("{bad-json", encoding="utf-8")

    with pytest.raises(ConfigError, match="invalid sync map file"):
        await sdk.map_sync(plan_id=sync_result.sync_map.plan_id, dry_run=True)


@pytest.mark.asyncio
async def test_map_sync_skips_partial_or_mismatched_metadata(tmp_path: Path, sample_plan: Plan) -> None:
    provider = FakeProvider()
    config = _make_config(tmp_path)
    _write_plan(config, sample_plan)
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=config)
    sync_result = await sdk.sync(sample_plan)
    plan_id = sync_result.sync_map.plan_id

    await provider.create_item(
        CreateItemInput(
            title="Mismatched PLAN_ID",
            body=(f"PLANPILOT_META_V1\nPLAN_ID:{plan_id}x\nITEM_ID:BAD1\nEND_PLANPILOT_META\n## Goal\n- ignored\n"),
            item_type=PlanItemType.TASK,
            labels=[sdk._config.label],
        )
    )
    await provider.create_item(
        CreateItemInput(
            title="Missing ITEM_ID",
            body=f"PLANPILOT_META_V1\nPLAN_ID:{plan_id}\nEND_PLANPILOT_META\n",
            item_type=PlanItemType.TASK,
            labels=[sdk._config.label],
        )
    )

    result = await sdk.map_sync(plan_id=plan_id, dry_run=True)

    assert "BAD1" not in result.sync_map.entries
    assert len(result.sync_map.entries) == len(sample_plan.items)


@pytest.mark.asyncio
async def test_map_sync_apply_persists_split_plan_files(tmp_path: Path, sample_plan: Plan) -> None:
    provider = FakeProvider()
    config = _make_split_config(tmp_path)
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=config)
    sync_result = await sdk.sync(sample_plan)

    result = await sdk.map_sync(plan_id=sync_result.sync_map.plan_id, dry_run=False)

    assert result.plan_items_synced == len(sample_plan.items)
    assert config.plan_paths.epics is not None and config.plan_paths.epics.exists()
    assert config.plan_paths.stories is not None and config.plan_paths.stories.exists()
    assert config.plan_paths.tasks is not None and config.plan_paths.tasks.exists()

    epic_payload = json.loads(config.plan_paths.epics.read_text(encoding="utf-8"))
    story_payload = json.loads(config.plan_paths.stories.read_text(encoding="utf-8"))
    task_payload = json.loads(config.plan_paths.tasks.read_text(encoding="utf-8"))

    assert len(epic_payload) + len(story_payload) + len(task_payload) == len(sample_plan.items)
    merged = {item["id"]: item for item in [*epic_payload, *story_payload, *task_payload]}
    assert sorted(merged.keys()) == ["E1", "S1", "T1"]


@pytest.mark.asyncio
async def test_map_sync_apply_plan_persist_write_error_raises_sync_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample_plan: Plan,
) -> None:
    provider = FakeProvider()
    config = _make_split_config(tmp_path)
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=config)
    sync_result = await sdk.sync(sample_plan)
    original_write_text = Path.write_text

    def _boom(
        self: Path,
        data: str,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> int:
        if self == config.plan_paths.tasks:
            raise OSError("disk full")
        return original_write_text(self, data, encoding=encoding, errors=errors, newline=newline)

    monkeypatch.setattr(Path, "write_text", _boom)

    with pytest.raises(SyncError, match="failed to persist plan files"):
        await sdk.map_sync(plan_id=sync_result.sync_map.plan_id, dry_run=False)
