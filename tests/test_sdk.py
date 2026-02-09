from __future__ import annotations

import json
from pathlib import Path

import pytest

from planpilot.contracts.config import PlanPaths, PlanPilotConfig
from planpilot.contracts.exceptions import ConfigError, PlanLoadError, PlanValidationError, ProviderError, SyncError
from planpilot.contracts.item import CreateItemInput, Item
from planpilot.contracts.plan import Plan, PlanItem, PlanItemType
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
