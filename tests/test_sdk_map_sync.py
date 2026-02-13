from __future__ import annotations

import json
from pathlib import Path

import pytest

from planpilot.cli.persistence.remote_plan import persist_plan_from_remote
from planpilot.cli.persistence.sync_map import persist_sync_map
from planpilot.core.contracts.config import PlanPaths, PlanPilotConfig
from planpilot.core.contracts.exceptions import ConfigError, ProviderError, SyncError
from planpilot.core.contracts.item import CreateItemInput
from planpilot.core.contracts.plan import Plan, PlanItemType
from planpilot.core.engine.progress import SyncProgress
from planpilot.core.map_sync import RemotePlanParser
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


class _SpyProgress(SyncProgress):
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def phase_start(self, phase: str, total: int | None = None) -> None:
        self.events.append(("start", phase))

    def item_done(self, phase: str) -> None:
        self.events.append(("item", phase))

    def phase_done(self, phase: str) -> None:
        self.events.append(("done", phase))

    def phase_error(self, phase: str, error: BaseException) -> None:
        self.events.append(("error", phase))


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
    persist_sync_map(sync_map=sync_result.sync_map, sync_path=config.sync_path, dry_run=False)
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
    persist_sync_map(sync_map=sync_result.sync_map, sync_path=config.sync_path, dry_run=False)
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
    assert config.sync_path.exists()


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
async def test_map_sync_apply_does_not_persist_split_plan_files(tmp_path: Path, sample_plan: Plan) -> None:
    provider = FakeProvider()
    config = _make_split_config(tmp_path)
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=config)
    sync_result = await sdk.sync(sample_plan)

    result = await sdk.map_sync(plan_id=sync_result.sync_map.plan_id, dry_run=False)

    assert result.plan_items_synced == len(sample_plan.items)
    assert config.plan_paths.epics is not None and config.plan_paths.epics.exists() is False
    assert config.plan_paths.stories is not None and config.plan_paths.stories.exists() is False
    assert config.plan_paths.tasks is not None and config.plan_paths.tasks.exists() is False


@pytest.mark.asyncio
async def test_persist_plan_from_remote_write_error_raises_sync_error(
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
        result = await sdk.map_sync(plan_id=sync_result.sync_map.plan_id, dry_run=False)
        persist_plan_from_remote(items=result.remote_plan_items, plan_paths=config.plan_paths)


@pytest.mark.asyncio
async def test_discover_remote_plan_ids_surfaces_provider_error(tmp_path: Path) -> None:
    class _FailingSearchProvider(FakeProvider):
        async def search_items(self, filters):  # type: ignore[override]
            raise ProviderError("search failed")

    sdk = PlanPilot(provider=_FailingSearchProvider(), renderer=FakeRenderer(), config=_make_config(tmp_path))

    with pytest.raises(ProviderError, match="search failed"):
        await sdk.discover_remote_plan_ids()


@pytest.mark.asyncio
async def test_discover_remote_plan_ids_provider_error_emits_phase_error(tmp_path: Path) -> None:
    class _FailingSearchProvider(FakeProvider):
        async def search_items(self, filters):  # type: ignore[override]
            raise ProviderError("search failed")

    progress = _SpyProgress()
    sdk = PlanPilot(
        provider=_FailingSearchProvider(),
        renderer=FakeRenderer(),
        config=_make_config(tmp_path),
        progress=progress,
    )

    with pytest.raises(ProviderError, match="search failed"):
        await sdk.discover_remote_plan_ids()

    assert ("error", "Map Plan IDs") in progress.events


@pytest.mark.asyncio
async def test_map_sync_surfaces_provider_error(tmp_path: Path) -> None:
    class _FailingSearchProvider(FakeProvider):
        async def search_items(self, filters):  # type: ignore[override]
            raise ProviderError("search failed")

    sdk = PlanPilot(provider=_FailingSearchProvider(), renderer=FakeRenderer(), config=_make_config(tmp_path))

    with pytest.raises(ProviderError, match="search failed"):
        await sdk.map_sync(plan_id="abc123", dry_run=True)


@pytest.mark.asyncio
async def test_map_sync_provider_error_emits_phase_error(tmp_path: Path) -> None:
    class _FailingSearchProvider(FakeProvider):
        async def search_items(self, filters):  # type: ignore[override]
            raise ProviderError("search failed")

    progress = _SpyProgress()
    sdk = PlanPilot(
        provider=_FailingSearchProvider(),
        renderer=FakeRenderer(),
        config=_make_config(tmp_path),
        progress=progress,
    )

    with pytest.raises(ProviderError, match="search failed"):
        await sdk.map_sync(plan_id="abc123", dry_run=True)

    assert ("error", "Map Discover") in progress.events


@pytest.mark.asyncio
async def test_map_sync_progress_marks_skipped_mismatched_and_missing_item_id(
    tmp_path: Path,
    sample_plan: Plan,
) -> None:
    provider = FakeProvider()
    config = _make_config(tmp_path)
    _write_plan(config, sample_plan)
    progress = _SpyProgress()
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=config, progress=progress)
    sync_result = await sdk.sync(sample_plan)
    plan_id = sync_result.sync_map.plan_id

    await provider.create_item(
        CreateItemInput(
            title="Mismatched PLAN_ID",
            body=f"PLANPILOT_META_V1\nPLAN_ID:{plan_id}x\nITEM_ID:BAD1\nEND_PLANPILOT_META\n",
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

    await sdk.map_sync(plan_id=plan_id, dry_run=True)

    reconcile_items = [event for event in progress.events if event == ("item", "Map Reconcile")]
    assert len(reconcile_items) >= len(sample_plan.items) + 2


def test_persist_plan_from_remote_builds_sub_item_ids_and_skips_missing_split_paths(tmp_path: Path) -> None:
    config = PlanPilotConfig(
        provider="github",
        target="owner/repo",
        board_url="https://github.com/orgs/owner/projects/1",
        plan_paths=PlanPaths(
            epics=tmp_path / "epics.json",
            stories=None,
            tasks=tmp_path / "tasks.json",
        ),
        sync_path=tmp_path / "sync-map.json",
    )
    parser = RemotePlanParser()

    epic = parser.plan_item_from_remote(
        item_id="E1",
        metadata={"ITEM_TYPE": "EPIC"},
        title="Epic",
        body="## Goal\n- g\n## Requirements\n- r\n## Acceptance Criteria\n- a\n",
    )
    story = parser.plan_item_from_remote(
        item_id="S1",
        metadata={"ITEM_TYPE": "STORY", "PARENT_ID": "E1"},
        title="Story",
        body="## Goal\n- g\n## Requirements\n- r\n## Acceptance Criteria\n- a\n",
    )
    task = parser.plan_item_from_remote(
        item_id="T1",
        metadata={"ITEM_TYPE": "TASK", "PARENT_ID": "S1"},
        title="Task",
        body="## Goal\n- g\n## Requirements\n- r\n## Acceptance Criteria\n- a\n",
    )

    persist_plan_from_remote(items=[task, story, epic], plan_paths=config.plan_paths)

    assert config.plan_paths.epics is not None and config.plan_paths.epics.exists()
    assert config.plan_paths.tasks is not None and config.plan_paths.tasks.exists()
    epic_payload = json.loads(config.plan_paths.epics.read_text(encoding="utf-8"))
    task_payload = json.loads(config.plan_paths.tasks.read_text(encoding="utf-8"))
    assert epic_payload[0]["sub_item_ids"] == ["S1"]
    assert task_payload[0]["id"] == "T1"


def test_plan_type_rank_and_remote_item_type_fallbacks(tmp_path: Path) -> None:
    assert RemotePlanParser.resolve_remote_item_type(item_id="x", metadata={"ITEM_TYPE": "epic"}) is PlanItemType.EPIC
    assert RemotePlanParser.resolve_remote_item_type(item_id="epic-1", metadata={}) is PlanItemType.EPIC
    assert RemotePlanParser.resolve_remote_item_type(item_id="story-1", metadata={}) is PlanItemType.STORY
    assert RemotePlanParser.resolve_remote_item_type(item_id="task-1", metadata={}) is PlanItemType.TASK


def test_plan_item_from_remote_defaults_and_markdown_parsers() -> None:
    parser = RemotePlanParser()

    item = parser.plan_item_from_remote(
        item_id="task-1",
        metadata={},
        title="No sections",
        body="plain body with no markdown headings",
    )

    assert item.goal == "(migrated from remote)"
    assert item.requirements == ["(migrated from remote)"]
    assert item.acceptance_criteria == ["(migrated from remote)"]

    sections = RemotePlanParser.extract_markdown_sections("## Goal\nline\n\n## Requirements\n- first\nplain")
    assert sections["Goal"] == "line"
    assert sections["Requirements"] == "- first\nplain"

    assert RemotePlanParser.parse_bullets(None) == []
    assert RemotePlanParser.parse_bullets("\n") == []
    assert RemotePlanParser.parse_bullets("- one\n* two\nthree") == ["one", "two", "three"]
