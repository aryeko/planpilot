from __future__ import annotations

import json
from pathlib import Path

import pytest

from planpilot.contracts.config import PlanPaths, PlanPilotConfig
from planpilot.contracts.exceptions import ConfigError
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
    provider.items[e1_provider_id]._key = "#4242"
    provider.items[e1_provider_id]._url = "https://fake/issues/4242"

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
async def test_map_sync_ignores_discovered_items_not_in_local_plan(tmp_path: Path, sample_plan: Plan) -> None:
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

    assert "EXTERNAL" not in result.sync_map.entries


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
