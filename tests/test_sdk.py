from __future__ import annotations

import json
from pathlib import Path

import pytest

from planpilot.contracts.config import PlanPaths, PlanPilotConfig
from planpilot.contracts.exceptions import ConfigError, PlanLoadError, PlanValidationError, ProviderError, SyncError
from planpilot.contracts.item import CreateItemInput, Item, ItemSearchFilters
from planpilot.contracts.plan import Plan, PlanItem, PlanItemType
from planpilot.plan import PlanHasher
from planpilot.sdk import PlanPilot, load_config, load_plan
from tests.fakes.provider import FakeProvider
from tests.fakes.renderer import FakeRenderer


class SpyProvider(FakeProvider):
    def __init__(self) -> None:
        super().__init__()
        self.enter_calls = 0
        self.exit_calls = 0

    async def __aenter__(self) -> SpyProvider:
        self.enter_calls += 1
        return await super().__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[override]
        self.exit_calls += 1
        await super().__aexit__(exc_type, exc_val, exc_tb)


class FailingCreateProvider(SpyProvider):
    async def create_item(self, input: CreateItemInput) -> Item:
        raise ProviderError("boom")


class _FakeTokenResolver:
    def __init__(self, token: str = "token-123") -> None:
        self._token = token

    async def resolve(self) -> str:
        return self._token


def _make_config(tmp_path: Path, *, plan_path: Path | None = None) -> PlanPilotConfig:
    return PlanPilotConfig(
        provider="github",
        target="owner/repo",
        board_url="https://github.com/orgs/owner/projects/1",
        plan_paths=PlanPaths(unified=plan_path or tmp_path / "plan.json"),
        sync_path=tmp_path / "sync-map.json",
    )


def _write_plan_and_get_id(tmp_path: Path) -> tuple[PlanPilotConfig, str]:
    plan = Plan(items=[PlanItem(id="E1", type=PlanItemType.EPIC, title="Epic")])
    return _write_custom_plan_and_get_id(tmp_path, plan)


def _write_custom_plan_and_get_id(tmp_path: Path, plan: Plan) -> tuple[PlanPilotConfig, str]:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    config = _make_config(tmp_path, plan_path=plan_path)
    return config, PlanHasher().compute_plan_id(plan)


def _metadata_body(
    plan_id: str,
    item_id: str,
    *,
    item_type: PlanItemType = PlanItemType.TASK,
    parent_id: str | None = None,
    with_metadata: bool = True,
) -> str:
    if not with_metadata:
        return "# Title"
    return "\n".join(
        [
            "PLANPILOT_META_V1",
            f"PLAN_ID:{plan_id}",
            f"ITEM_ID:{item_id}",
            f"ITEM_TYPE:{item_type.value}",
            f"PARENT_ID:{parent_id or ''}",
            "END_PLANPILOT_META",
            "",
            "# Title",
        ]
    )


async def _create_clean_item(
    provider: FakeProvider,
    config: PlanPilotConfig,
    *,
    plan_id: str,
    item_id: str,
    item_type: PlanItemType = PlanItemType.TASK,
    parent_id: str | None = None,
    with_metadata: bool = True,
) -> Item:
    return await provider.create_item(
        CreateItemInput(
            title=f"Item {item_id}",
            body=_metadata_body(
                plan_id,
                item_id,
                item_type=item_type,
                parent_id=parent_id,
                with_metadata=with_metadata,
            ),
            item_type=item_type,
            labels=[config.label],
        )
    )


class RetryDeleteProvider(FakeProvider):
    def __init__(self, *, retry_item_id: str) -> None:
        super().__init__()
        self._retry_item_id = retry_item_id
        self.retry_attempts = 0

    async def delete_item(self, item_id: str) -> None:
        if item_id == self._retry_item_id and self.retry_attempts == 0:
            self.retry_attempts += 1
            self.delete_calls.append(item_id)
            raise ProviderError("parent has sub-issues")
        await super().delete_item(item_id)


class AlwaysFailDeleteProvider(FakeProvider):
    async def delete_item(self, item_id: str) -> None:
        self.delete_calls.append(item_id)
        raise ProviderError("delete failed")


class FailingSearchProvider(FakeProvider):
    async def search_items(self, filters: ItemSearchFilters) -> list[Item]:
        raise ProviderError("search failed")


@pytest.mark.asyncio
async def test_from_config_wires_renderer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    renderer = FakeRenderer()

    def _fake_create_renderer(name: str) -> FakeRenderer:
        assert name == "markdown"
        return renderer

    monkeypatch.setattr("planpilot.sdk.create_renderer", _fake_create_renderer)

    sdk = await PlanPilot.from_config(config)

    assert sdk._provider is None
    assert sdk._renderer is renderer
    assert sdk._config is config


@pytest.mark.asyncio
async def test_from_config_unknown_renderer_raises_config_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = _make_config(tmp_path)

    def _boom(_: str) -> FakeRenderer:
        raise ValueError("unknown renderer")

    monkeypatch.setattr("planpilot.sdk.create_renderer", _boom)

    with pytest.raises(ConfigError, match="unknown renderer"):
        await PlanPilot.from_config(config)


@pytest.mark.asyncio
async def test_sync_happy_path_persists_sync_map(tmp_path: Path, sample_plan: Plan) -> None:
    provider = SpyProvider()
    renderer = FakeRenderer()
    config = _make_config(tmp_path)

    sdk = PlanPilot(provider=provider, renderer=renderer, config=config)
    result = await sdk.sync(sample_plan)

    assert result.dry_run is False
    assert provider.enter_calls == 1
    assert provider.exit_calls == 1

    assert config.sync_path.exists()
    persisted = json.loads(config.sync_path.read_text(encoding="utf-8"))
    assert persisted["target"] == config.target
    assert persisted["board_url"] == config.board_url
    assert len(persisted["entries"]) == len(sample_plan.items)


@pytest.mark.asyncio
async def test_sync_loads_plan_from_config_when_not_provided(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "E1",
                        "type": "EPIC",
                        "title": "Epic",
                        "goal": "Goal",
                        "requirements": ["R1"],
                        "acceptance_criteria": ["AC1"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    provider = SpyProvider()
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=_make_config(tmp_path, plan_path=plan_path))

    result = await sdk.sync()

    assert "E1" in result.sync_map.entries


@pytest.mark.asyncio
async def test_sync_dry_run_uses_dry_run_provider_and_persists_dry_run_map(tmp_path: Path, sample_plan: Plan) -> None:
    provider = SpyProvider()
    config = _make_config(tmp_path)

    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=config)
    result = await sdk.sync(sample_plan, dry_run=True)

    assert result.dry_run is True
    assert provider.enter_calls == 0
    assert provider.exit_calls == 0

    dry_run_path = Path(f"{config.sync_path}.dry-run")
    assert dry_run_path.exists()
    persisted = json.loads(dry_run_path.read_text(encoding="utf-8"))
    assert persisted["entries"]["E1"]["id"].startswith("dry-run-")


@pytest.mark.asyncio
async def test_sync_propagates_plan_load_error(tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    sdk = PlanPilot(provider=SpyProvider(), renderer=FakeRenderer(), config=config)

    with pytest.raises(PlanLoadError):
        await sdk.sync()


@pytest.mark.asyncio
async def test_sync_propagates_plan_validation_error(tmp_path: Path) -> None:
    invalid_plan = Plan(items=[PlanItem(id="E1", type=PlanItemType.EPIC, title="Epic")])
    provider = SpyProvider()
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=_make_config(tmp_path))

    with pytest.raises(PlanValidationError):
        await sdk.sync(invalid_plan)

    assert provider.enter_calls == 0
    assert provider.exit_calls == 0


@pytest.mark.asyncio
async def test_sync_calls_provider_exit_on_engine_error(tmp_path: Path, sample_plan: Plan) -> None:
    provider = FailingCreateProvider()
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=_make_config(tmp_path))

    with pytest.raises(ProviderError):
        await sdk.sync(sample_plan)

    assert provider.enter_calls == 1
    assert provider.exit_calls == 1


@pytest.mark.asyncio
async def test_sync_builds_provider_via_token_resolver_and_factory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, sample_plan: Plan
) -> None:
    provider = SpyProvider()

    def _fake_create_provider(name: str, **kwargs: object) -> SpyProvider:
        assert name == "github"
        assert kwargs["token"] == "resolved-token"
        return provider

    monkeypatch.setattr("planpilot.sdk.create_token_resolver", lambda _: _FakeTokenResolver("resolved-token"))
    monkeypatch.setattr("planpilot.sdk.create_provider", _fake_create_provider)

    sdk = PlanPilot(provider=None, renderer=FakeRenderer(), config=_make_config(tmp_path))
    result = await sdk.sync(sample_plan)

    assert result.dry_run is False
    assert provider.enter_calls == 1
    assert provider.exit_calls == 1


@pytest.mark.asyncio
async def test_sync_provider_factory_value_error_is_wrapped_as_config_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, sample_plan: Plan
) -> None:
    monkeypatch.setattr("planpilot.sdk.create_token_resolver", lambda _: _FakeTokenResolver())

    def _boom(*args: object, **kwargs: object) -> SpyProvider:
        raise ValueError("bad provider")

    monkeypatch.setattr("planpilot.sdk.create_provider", _boom)

    sdk = PlanPilot(provider=None, renderer=FakeRenderer(), config=_make_config(tmp_path))
    with pytest.raises(ConfigError, match="bad provider"):
        await sdk.sync(sample_plan)


@pytest.mark.asyncio
async def test_sync_persist_write_error_is_wrapped_as_sync_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, sample_plan: Plan
) -> None:
    sdk = PlanPilot(provider=SpyProvider(), renderer=FakeRenderer(), config=_make_config(tmp_path))
    original_write_text = Path.write_text

    def _boom(self: Path, *args: object, **kwargs: object) -> int:
        if self == sdk._config.sync_path:
            raise OSError("disk full")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", _boom)

    with pytest.raises(SyncError, match="failed to persist sync map"):
        await sdk.sync(sample_plan)


@pytest.mark.asyncio
async def test_clean_dry_run_discovers_but_does_not_delete(tmp_path: Path) -> None:
    config, plan_id = _write_plan_and_get_id(tmp_path)
    provider = SpyProvider()
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=config)

    await _create_clean_item(provider, config, plan_id=plan_id, item_id="E1")
    await _create_clean_item(provider, config, plan_id=plan_id, item_id="S1")
    await _create_clean_item(provider, config, plan_id=plan_id, item_id="T1")

    result = await sdk.clean(dry_run=True)

    assert result.items_deleted == 3
    assert result.dry_run is True
    assert provider.delete_calls == []
    assert len(provider.items) == 3


@pytest.mark.asyncio
async def test_clean_apply_discovers_and_deletes(tmp_path: Path) -> None:
    config, plan_id = _write_plan_and_get_id(tmp_path)
    provider = SpyProvider()
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=config)

    await _create_clean_item(provider, config, plan_id=plan_id, item_id="E1")
    await _create_clean_item(provider, config, plan_id=plan_id, item_id="S1")
    await _create_clean_item(provider, config, plan_id=plan_id, item_id="T1")

    result = await sdk.clean(dry_run=False)

    assert result.items_deleted == 3
    assert len(provider.delete_calls) == 3
    assert provider.items == {}


@pytest.mark.asyncio
async def test_clean_filters_by_plan_id(tmp_path: Path) -> None:
    config, plan_id = _write_plan_and_get_id(tmp_path)
    provider = SpyProvider()
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=config)

    matching_a = await _create_clean_item(provider, config, plan_id=plan_id, item_id="E1")
    matching_b = await _create_clean_item(provider, config, plan_id=plan_id, item_id="S1")
    other = await _create_clean_item(provider, config, plan_id="other-plan-id", item_id="X1")

    result = await sdk.clean()

    assert result.items_deleted == 2
    assert set(provider.delete_calls) == {matching_a.id, matching_b.id}
    assert list(provider.items) == [other.id]


@pytest.mark.asyncio
async def test_clean_all_plans_ignores_plan_id(tmp_path: Path) -> None:
    config, _ = _write_plan_and_get_id(tmp_path)
    provider = SpyProvider()
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=config)

    await _create_clean_item(provider, config, plan_id="plan-a", item_id="E1")
    await _create_clean_item(provider, config, plan_id="plan-b", item_id="E2")

    result = await sdk.clean(all_plans=True)

    assert result.items_deleted == 2
    assert len(provider.delete_calls) == 2
    assert provider.items == {}


@pytest.mark.asyncio
async def test_clean_all_plans_skips_items_without_metadata(tmp_path: Path) -> None:
    config, _ = _write_plan_and_get_id(tmp_path)
    provider = SpyProvider()
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=config)

    with_metadata = await _create_clean_item(provider, config, plan_id="plan-a", item_id="E1")
    without_metadata = await _create_clean_item(
        provider, config, plan_id="plan-a", item_id="NO_META", with_metadata=False
    )

    result = await sdk.clean(all_plans=True)

    assert result.items_deleted == 1
    assert provider.delete_calls == [with_metadata.id]
    assert list(provider.items) == [without_metadata.id]


@pytest.mark.asyncio
async def test_clean_returns_zero_when_no_matches(tmp_path: Path) -> None:
    config, _ = _write_plan_and_get_id(tmp_path)
    provider = SpyProvider()
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=config)

    result = await sdk.clean()

    assert result.items_deleted == 0
    assert provider.delete_calls == []


@pytest.mark.asyncio
async def test_clean_retries_parent_deletion_after_children(tmp_path: Path) -> None:
    config, plan_id = _write_plan_and_get_id(tmp_path)
    setup_provider = FakeProvider()
    parent = await _create_clean_item(setup_provider, config, plan_id=plan_id, item_id="E1")
    child = await _create_clean_item(setup_provider, config, plan_id=plan_id, item_id="S1")

    provider = RetryDeleteProvider(retry_item_id=parent.id)
    provider.items = dict(setup_provider.items)
    provider._next_number = setup_provider._next_number
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=config)

    result = await sdk.clean(dry_run=False)

    assert result.items_deleted == 2
    assert provider.retry_attempts == 1
    assert provider.delete_calls == [child.id, parent.id, parent.id]
    assert provider.items == {}


@pytest.mark.asyncio
async def test_clean_skips_metadata_plan_mismatch_even_if_body_contains_plan_id(tmp_path: Path) -> None:
    config, plan_id = _write_plan_and_get_id(tmp_path)
    provider = SpyProvider()
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=config)

    await provider.create_item(
        CreateItemInput(
            title="Mismatched metadata plan",
            body="\n".join(
                [
                    "PLANPILOT_META_V1",
                    "PLAN_ID:other-plan",
                    "ITEM_ID:S1",
                    "END_PLANPILOT_META",
                    "",
                    f"Contains PLAN_ID:{plan_id} outside metadata.",
                ]
            ),
            item_type=PlanItemType.STORY,
            labels=[config.label],
        )
    )

    result = await sdk.clean()

    assert result.items_deleted == 0
    assert provider.delete_calls == []


@pytest.mark.asyncio
async def test_clean_unwraps_provider_error_from_search(tmp_path: Path) -> None:
    config, _ = _write_plan_and_get_id(tmp_path)
    sdk = PlanPilot(provider=FailingSearchProvider(), renderer=FakeRenderer(), config=config)

    with pytest.raises(ProviderError, match="search failed"):
        await sdk.clean()


@pytest.mark.asyncio
async def test_clean_raises_when_delete_retry_fails_twice(tmp_path: Path) -> None:
    config, plan_id = _write_plan_and_get_id(tmp_path)
    provider = AlwaysFailDeleteProvider()
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=config)

    item = await _create_clean_item(provider, config, plan_id=plan_id, item_id="E1")

    with pytest.raises(ProviderError, match="delete failed"):
        await sdk.clean(dry_run=False)

    assert provider.delete_calls == [item.id]


@pytest.mark.asyncio
async def test_clean_deletes_leaf_first_for_deep_hierarchy(tmp_path: Path) -> None:
    plan = Plan(
        items=[
            PlanItem(id="E1", type=PlanItemType.EPIC, title="Epic"),
            PlanItem(id="S1", type=PlanItemType.STORY, title="Story", parent_id="E1"),
            PlanItem(id="T1", type=PlanItemType.TASK, title="Task", parent_id="S1"),
        ]
    )
    config, plan_id = _write_custom_plan_and_get_id(tmp_path, plan)
    provider = SpyProvider()
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=config)

    epic = await _create_clean_item(provider, config, plan_id=plan_id, item_id="E1", item_type=PlanItemType.EPIC)
    story = await _create_clean_item(
        provider, config, plan_id=plan_id, item_id="S1", item_type=PlanItemType.STORY, parent_id="E1"
    )
    task = await _create_clean_item(
        provider, config, plan_id=plan_id, item_id="T1", item_type=PlanItemType.TASK, parent_id="S1"
    )

    result = await sdk.clean(dry_run=False)

    assert result.items_deleted == 3
    assert provider.delete_calls == [task.id, story.id, epic.id]


@pytest.mark.asyncio
async def test_clean_all_plans_uses_metadata_parent_id_for_leaf_first_order(tmp_path: Path) -> None:
    config, _ = _write_plan_and_get_id(tmp_path)
    provider = SpyProvider()
    sdk = PlanPilot(provider=provider, renderer=FakeRenderer(), config=config)

    parent_a = await _create_clean_item(provider, config, plan_id="plan-a", item_id="E-A", item_type=PlanItemType.EPIC)
    child_a = await _create_clean_item(
        provider,
        config,
        plan_id="plan-a",
        item_id="T-A",
        item_type=PlanItemType.TASK,
        parent_id="E-A",
    )
    parent_b = await _create_clean_item(provider, config, plan_id="plan-b", item_id="E-B", item_type=PlanItemType.EPIC)
    child_b = await _create_clean_item(
        provider,
        config,
        plan_id="plan-b",
        item_id="T-B",
        item_type=PlanItemType.TASK,
        parent_id="E-B",
    )

    result = await sdk.clean(all_plans=True)

    assert result.items_deleted == 4
    assert provider.delete_calls.index(child_a.id) < provider.delete_calls.index(parent_a.id)
    assert provider.delete_calls.index(child_b.id) < provider.delete_calls.index(parent_b.id)


def test_load_config_reads_json_and_resolves_relative_paths(tmp_path: Path) -> None:
    config_dir = tmp_path / "cfg"
    config_dir.mkdir()
    config_path = config_dir / "planpilot.json"
    config_path.write_text(
        json.dumps(
            {
                "provider": "github",
                "target": "owner/repo",
                "board_url": "https://github.com/orgs/owner/projects/1",
                "plan_paths": {"unified": "plans/plan.json"},
                "sync_path": "out/sync-map.json",
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.plan_paths.unified == config_dir / "plans/plan.json"
    assert config.sync_path == config_dir / "out/sync-map.json"


def test_load_config_keeps_absolute_paths_absolute(tmp_path: Path) -> None:
    config_path = tmp_path / "planpilot.json"
    absolute_plan = (tmp_path / "plans" / "plan.json").resolve()
    absolute_sync = (tmp_path / "out" / "sync-map.json").resolve()
    config_path.write_text(
        json.dumps(
            {
                "provider": "github",
                "target": "owner/repo",
                "board_url": "https://github.com/orgs/owner/projects/1",
                "plan_paths": {"unified": str(absolute_plan)},
                "sync_path": str(absolute_sync),
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.plan_paths.unified == absolute_plan
    assert config.sync_path == absolute_sync


def test_load_config_invalid_json_raises_config_error(tmp_path: Path) -> None:
    config_path = tmp_path / "planpilot.json"
    config_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(config_path)


def test_load_config_invalid_schema_raises_config_error(tmp_path: Path) -> None:
    config_path = tmp_path / "planpilot.json"
    config_path.write_text(json.dumps({"provider": "github"}), encoding="utf-8")

    with pytest.raises(ConfigError, match="invalid config"):
        load_config(config_path)


def test_load_config_read_os_error_raises_config_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = tmp_path / "planpilot.json"
    config_path.write_text("{}", encoding="utf-8")
    original_read_text = Path.read_text

    def _boom(self: Path, *args: object, **kwargs: object) -> str:
        if self == config_path:
            raise OSError("permission denied")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _boom)

    with pytest.raises(ConfigError, match="failed reading config file"):
        load_config(config_path)


def test_load_config_rejects_user_project_with_issue_type_strategy(tmp_path: Path) -> None:
    config_path = tmp_path / "planpilot.json"
    config_path.write_text(
        json.dumps(
            {
                "provider": "github",
                "target": "owner/repo",
                "board_url": "https://github.com/users/alice/projects/1",
                "plan_paths": {"unified": "plan.json"},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="create_type_strategy"):
        load_config(config_path)


def test_load_config_invalid_github_board_url_is_wrapped_as_config_error(tmp_path: Path) -> None:
    config_path = tmp_path / "planpilot.json"
    config_path.write_text(
        json.dumps(
            {
                "provider": "github",
                "target": "owner/repo",
                "board_url": "https://example.com/not-a-github-project",
                "plan_paths": {"unified": "plan.json"},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="Unsupported project URL"):
        load_config(config_path)


def test_load_config_invalid_create_type_strategy_raises_config_error(tmp_path: Path) -> None:
    config_path = tmp_path / "planpilot.json"
    config_path.write_text(
        json.dumps(
            {
                "provider": "github",
                "target": "owner/repo",
                "board_url": "https://github.com/orgs/owner/projects/1",
                "plan_paths": {"unified": "plan.json"},
                "field_config": {"create_type_strategy": "invalid"},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="create_type_strategy"):
        load_config(config_path)


def test_load_config_non_github_skips_github_specific_validation(tmp_path: Path) -> None:
    config_path = tmp_path / "planpilot.json"
    config_path.write_text(
        json.dumps(
            {
                "provider": "jira",
                "target": "owner/repo",
                "board_url": "not-a-github-project-url",
                "plan_paths": {"unified": "plan.json"},
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.provider == "jira"


def test_load_config_does_not_wrap_unexpected_url_parser_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "planpilot.json"
    config_path.write_text(
        json.dumps(
            {
                "provider": "github",
                "target": "owner/repo",
                "board_url": "https://github.com/orgs/owner/projects/1",
                "plan_paths": {"unified": "plan.json"},
            }
        ),
        encoding="utf-8",
    )

    def _boom(_: str) -> tuple[str, str, int]:
        raise RuntimeError("unexpected parser failure")

    monkeypatch.setattr("planpilot.sdk.parse_project_url", _boom)

    with pytest.raises(RuntimeError, match="unexpected parser failure"):
        load_config(config_path)


def test_load_plan_invalid_paths_raise_plan_load_error() -> None:
    with pytest.raises(PlanLoadError, match="invalid plan paths"):
        load_plan()


def test_load_plan_convenience_wrapper_loads_unified_file(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "E1",
                        "type": "EPIC",
                        "title": "Epic",
                        "goal": "Goal",
                        "requirements": ["R1"],
                        "acceptance_criteria": ["AC1"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    plan = load_plan(unified=plan_path)

    assert [item.id for item in plan.items] == ["E1"]
