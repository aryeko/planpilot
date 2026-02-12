"""SDK composition root for PlanPilot v2."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from planpilot.auth import create_token_resolver
from planpilot.contracts.config import PlanPaths, PlanPilotConfig
from planpilot.contracts.exceptions import ConfigError, PlanLoadError, ProjectURLError, ProviderError, SyncError
from planpilot.contracts.item import ItemSearchFilters
from planpilot.contracts.plan import Plan
from planpilot.contracts.provider import Provider
from planpilot.contracts.renderer import BodyRenderer
from planpilot.contracts.sync import MapSyncResult, SyncMap, SyncResult, to_sync_entry
from planpilot.engine import SyncEngine
from planpilot.engine.progress import SyncProgress
from planpilot.engine.utils import parse_metadata_block
from planpilot.plan import PlanHasher, PlanLoader, PlanValidator
from planpilot.providers.dry_run import DryRunProvider
from planpilot.providers.factory import create_provider
from planpilot.providers.github.mapper import parse_project_url
from planpilot.renderers import create_renderer


def _resolve_path(value: Path | None, *, base_dir: Path) -> Path | None:
    if value is None:
        return None
    if value.is_absolute():
        return value
    return (base_dir / value).resolve()


def _validate_provider_specific_config(config: PlanPilotConfig) -> None:
    if config.provider != "github":
        return

    try:
        owner_type, _, _ = parse_project_url(config.board_url)
    except ProjectURLError as exc:
        raise ConfigError(str(exc)) from exc

    strategy = config.field_config.create_type_strategy
    if strategy not in {"issue-type", "label"}:
        raise ConfigError("field_config.create_type_strategy must be one of: issue-type, label")
    if owner_type == "user" and strategy != "label":
        raise ConfigError("GitHub user-owned projects require field_config.create_type_strategy='label'")


def load_config(path: str | Path) -> PlanPilotConfig:
    """Load and validate config from JSON, resolving relative paths against config directory."""
    config_path = Path(path).expanduser().resolve()
    config_dir = config_path.parent

    try:
        raw_payload: Any = json.loads(config_path.read_text(encoding="utf-8"))
        parsed = PlanPilotConfig.model_validate(raw_payload)
    except OSError as exc:
        raise ConfigError(f"failed reading config file: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in config file: {config_path}") from exc
    except ValidationError as exc:
        raise ConfigError(f"invalid config: {exc}") from exc

    resolved_paths = PlanPaths(
        epics=_resolve_path(parsed.plan_paths.epics, base_dir=config_dir),
        stories=_resolve_path(parsed.plan_paths.stories, base_dir=config_dir),
        tasks=_resolve_path(parsed.plan_paths.tasks, base_dir=config_dir),
        unified=_resolve_path(parsed.plan_paths.unified, base_dir=config_dir),
    )
    resolved_config = parsed.model_copy(
        update={
            "plan_paths": resolved_paths,
            "sync_path": _resolve_path(parsed.sync_path, base_dir=config_dir),
        }
    )
    _validate_provider_specific_config(resolved_config)
    return resolved_config


def load_plan(
    *,
    unified: str | Path | None = None,
    epics: str | Path | None = None,
    stories: str | Path | None = None,
    tasks: str | Path | None = None,
) -> Plan:
    """Load a plan from explicit path inputs."""
    try:
        paths = PlanPaths(
            unified=Path(unified) if unified is not None else None,
            epics=Path(epics) if epics is not None else None,
            stories=Path(stories) if stories is not None else None,
            tasks=Path(tasks) if tasks is not None else None,
        )
    except ValidationError as exc:
        raise PlanLoadError(f"invalid plan paths: {exc}") from exc

    return PlanLoader().load(paths)


class PlanPilot:
    """PlanPilot SDK public API."""

    def __init__(
        self,
        *,
        provider: Provider | None,
        renderer: BodyRenderer,
        config: PlanPilotConfig,
        progress: SyncProgress | None = None,
    ) -> None:
        self._provider = provider
        self._renderer = renderer
        self._config = config
        self._progress = progress

    @classmethod
    async def from_config(
        cls,
        config: PlanPilotConfig,
        *,
        renderer_name: str = "markdown",
        progress: SyncProgress | None = None,
    ) -> PlanPilot:
        try:
            renderer = create_renderer(renderer_name)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
        return cls(provider=None, renderer=renderer, config=config, progress=progress)

    async def sync(
        self,
        plan: Plan | None = None,
        *,
        dry_run: bool = False,
    ) -> SyncResult:
        loaded_plan = plan if plan is not None else PlanLoader().load(self._config.plan_paths)
        PlanValidator().validate(loaded_plan, mode=self._config.validation_mode)
        plan_id = PlanHasher().compute_plan_id(loaded_plan)

        try:
            if dry_run:
                provider: Provider = DryRunProvider()
                result = await SyncEngine(
                    provider, self._renderer, self._config, dry_run=True, progress=self._progress
                ).sync(loaded_plan, plan_id)
            else:
                provider = await self._resolve_apply_provider()
                async with provider:
                    result = await SyncEngine(
                        provider, self._renderer, self._config, dry_run=False, progress=self._progress
                    ).sync(loaded_plan, plan_id)
        except* ProviderError as provider_errors:
            raise provider_errors.exceptions[0] from None

        self._persist_sync_map(result.sync_map, dry_run=dry_run)
        return result

    async def discover_remote_plan_ids(self) -> list[str]:
        """Discover unique PLAN_ID values from provider metadata."""
        provider = await self._resolve_apply_provider()
        try:
            async with provider:
                items = await provider.search_items(ItemSearchFilters(labels=[self._config.label]))
        except* ProviderError as provider_errors:
            raise provider_errors.exceptions[0] from None

        plan_ids = {
            metadata["PLAN_ID"]
            for item in items
            for metadata in [parse_metadata_block(item.body)]
            if metadata.get("PLAN_ID")
        }
        return sorted(plan_ids)

    async def map_sync(self, *, plan_id: str, dry_run: bool = False) -> MapSyncResult:
        """Reconcile local sync-map from provider discovery for selected plan."""
        loaded_plan = PlanLoader().load(self._config.plan_paths)
        PlanValidator().validate(loaded_plan, mode=self._config.validation_mode)
        current = self._load_sync_map(plan_id=plan_id)
        plan_item_ids = {item.id for item in loaded_plan.items}

        provider = await self._resolve_apply_provider()
        try:
            async with provider:
                discovered_items = await provider.search_items(
                    ItemSearchFilters(labels=[self._config.label], body_contains=f"PLAN_ID:{plan_id}")
                )
        except* ProviderError as provider_errors:
            raise provider_errors.exceptions[0] from None

        desired_entries = {}
        for item in discovered_items:
            metadata = parse_metadata_block(item.body)
            if metadata.get("PLAN_ID") != plan_id:
                continue
            item_id = metadata.get("ITEM_ID")
            if not item_id or item_id not in plan_item_ids:
                continue
            desired_entries[item_id] = to_sync_entry(item)

        current_entries = current.entries
        added = sorted(item_id for item_id in desired_entries if item_id not in current_entries)
        removed = sorted(item_id for item_id in current_entries if item_id not in desired_entries)
        updated = sorted(
            item_id
            for item_id in desired_entries
            if item_id in current_entries and current_entries[item_id] != desired_entries[item_id]
        )

        reconciled = SyncMap(
            plan_id=plan_id,
            target=self._config.target,
            board_url=self._config.board_url,
            entries=desired_entries,
        )
        result = MapSyncResult(
            sync_map=reconciled,
            added=added,
            removed=removed,
            updated=updated,
            dry_run=dry_run,
        )
        if not dry_run:
            self._persist_sync_map(reconciled, dry_run=False)
        return result

    async def _resolve_apply_provider(self) -> Provider:
        if self._provider is not None:
            return self._provider

        token_resolver = create_token_resolver(self._config)
        token = await token_resolver.resolve()
        try:
            return create_provider(
                self._config.provider,
                target=self._config.target,
                token=token,
                board_url=self._config.board_url,
                label=self._config.label,
                field_config=self._config.field_config,
            )
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc

    def _persist_sync_map(self, sync_map: SyncMap, *, dry_run: bool) -> None:
        output_path = self._output_sync_path(dry_run=dry_run)
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(sync_map.model_dump_json(indent=2), encoding="utf-8")
        except OSError as exc:
            raise SyncError(f"failed to persist sync map: {output_path}") from exc

    def _output_sync_path(self, *, dry_run: bool) -> Path:
        if not dry_run:
            return self._config.sync_path
        return Path(f"{self._config.sync_path}.dry-run")

    def _load_sync_map(self, *, plan_id: str) -> SyncMap:
        path = self._config.sync_path
        if not path.exists():
            return SyncMap(plan_id=plan_id, target=self._config.target, board_url=self._config.board_url, entries={})
        try:
            payload: Any = json.loads(path.read_text(encoding="utf-8"))
            parsed = SyncMap.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise ConfigError(f"invalid sync map file: {path}") from exc
        return parsed
