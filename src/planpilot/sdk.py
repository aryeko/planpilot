"""SDK composition root for PlanPilot v2."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from planpilot.auth import create_token_resolver
from planpilot.clean import CleanDeletionPlanner
from planpilot.config.loader import load_config as _load_config
from planpilot.contracts.config import PlanPaths, PlanPilotConfig
from planpilot.contracts.exceptions import ConfigError, PlanLoadError, ProviderError, SyncError
from planpilot.contracts.item import Item, ItemSearchFilters
from planpilot.contracts.plan import Plan, PlanItem, PlanItemType
from planpilot.contracts.provider import Provider
from planpilot.contracts.renderer import BodyRenderer
from planpilot.contracts.sync import CleanResult, MapSyncResult, SyncEntry, SyncMap, SyncResult
from planpilot.engine import SyncEngine
from planpilot.engine.progress import SyncProgress
from planpilot.map_sync import MapSyncReconciler, RemotePlanParser, RemotePlanPersistence
from planpilot.metadata import parse_metadata_block
from planpilot.plan import PlanHasher as PlanHasher
from planpilot.plan import PlanLoader, PlanValidator
from planpilot.providers.dry_run import DryRunProvider
from planpilot.providers.factory import create_provider
from planpilot.renderers import create_renderer


def load_config(path: str | Path) -> PlanPilotConfig:
    """Load and validate config from JSON."""
    return _load_config(path)


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
        self._clean_planner = CleanDeletionPlanner()
        self._map_sync_parser = RemotePlanParser()
        self._map_sync_reconciler = MapSyncReconciler(parser=self._map_sync_parser)
        self._map_sync_persistence = RemotePlanPersistence()

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
                    provider,
                    self._renderer,
                    self._config,
                    dry_run=True,
                    progress=self._progress,
                ).sync(loaded_plan, plan_id)
            else:
                provider = await self._resolve_apply_provider()
                async with provider:
                    result = await SyncEngine(
                        provider,
                        self._renderer,
                        self._config,
                        dry_run=False,
                        progress=self._progress,
                    ).sync(loaded_plan, plan_id)
        except* ProviderError as provider_errors:
            raise provider_errors.exceptions[0] from None

        self._persist_sync_map(result.sync_map, dry_run=dry_run)
        return result

    async def discover_remote_plan_ids(self) -> list[str]:
        """Discover unique PLAN_ID values from provider metadata."""
        if self._progress is not None:
            self._progress.phase_start("Map Plan IDs")
        provider = await self._resolve_apply_provider()
        try:
            async with provider:
                items = await provider.search_items(ItemSearchFilters(labels=[self._config.label]))
        except* ProviderError as provider_errors:
            if self._progress is not None:
                self._progress.phase_error("Map Plan IDs", provider_errors.exceptions[0])
            raise provider_errors.exceptions[0] from None

        plan_ids = {
            metadata["PLAN_ID"]
            for item in items
            for metadata in [parse_metadata_block(item.body)]
            if metadata.get("PLAN_ID")
        }
        if self._progress is not None:
            self._progress.phase_done("Map Plan IDs")
        return sorted(plan_ids)

    async def map_sync(self, *, plan_id: str, dry_run: bool = False) -> MapSyncResult:
        """Reconcile local sync-map and bootstrap local plan from remote discovery."""
        current = self._load_sync_map(plan_id=plan_id)

        if self._progress is not None:
            self._progress.phase_start("Map Discover")
        provider = await self._resolve_apply_provider()
        try:
            async with provider:
                discovered_items = await provider.search_items(
                    ItemSearchFilters(labels=[self._config.label], body_contains=f"PLAN_ID:{plan_id}")
                )
        except* ProviderError as provider_errors:
            if self._progress is not None:
                self._progress.phase_error("Map Discover", provider_errors.exceptions[0])
            raise provider_errors.exceptions[0] from None
        if self._progress is not None:
            self._progress.phase_done("Map Discover")

        desired_entries: dict[str, SyncEntry]
        remote_plan_items: dict[str, PlanItem]
        if self._progress is not None:
            self._progress.phase_start("Map Reconcile", total=len(discovered_items))
        desired_entries, remote_plan_items = self._map_sync_reconciler.reconcile_discovered_items(
            discovered_items=discovered_items,
            plan_id=plan_id,
        )
        if self._progress is not None:
            for _ in discovered_items:
                self._progress.item_done("Map Reconcile")
            self._progress.phase_done("Map Reconcile")

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
            plan_items_synced=len(remote_plan_items),
            dry_run=dry_run,
        )
        if not dry_run:
            if self._progress is not None:
                self._progress.phase_start("Map Persist")
            self._persist_sync_map(reconciled, dry_run=False)
            self._persist_plan_from_remote(items=remote_plan_items.values())
            if self._progress is not None:
                self._progress.phase_done("Map Persist")
        return result

    async def clean(self, *, dry_run: bool = False, all_plans: bool = False) -> CleanResult:
        """Discover and delete all issues belonging to a plan.

        Always uses the real provider for discovery so dry-run accurately
        reflects what would be deleted.
        """
        loaded_plan: Plan | None = None
        if all_plans:
            plan_id = "all-plans"
        else:
            loaded_plan = PlanLoader().load(self._config.plan_paths)
            plan_id = PlanHasher().compute_plan_id(loaded_plan)

        try:
            provider = await self._resolve_apply_provider()
            async with provider:
                items_deleted = await self._discover_and_delete_items(
                    provider,
                    plan_id,
                    loaded_plan,
                    dry_run=dry_run,
                    all_plans=all_plans,
                )
        except* ProviderError as provider_errors:
            raise provider_errors.exceptions[0] from None

        return CleanResult(plan_id=plan_id, items_deleted=items_deleted, dry_run=dry_run)

    async def _discover_and_delete_items(
        self,
        provider: Provider,
        plan_id: str,
        plan: Plan | None,
        *,
        dry_run: bool,
        all_plans: bool = False,
    ) -> int:
        if all_plans:
            filters = ItemSearchFilters(labels=[self._config.label])
        else:
            filters = ItemSearchFilters(labels=[self._config.label], body_contains=f"PLAN_ID:{plan_id}")

        if self._progress is not None:
            self._progress.phase_start("Clean Discover")
        existing_items = await provider.search_items(filters)
        if self._progress is not None:
            self._progress.phase_done("Clean Discover")

        items_to_delete: list[Item] = []
        metadata_by_provider_id: dict[str, dict[str, str]] = {}
        if self._progress is not None:
            self._progress.phase_start("Clean Filter", total=len(existing_items))
        for item in existing_items:
            metadata = parse_metadata_block(item.body)
            if not all_plans and metadata.get("PLAN_ID") != plan_id:
                if self._progress is not None:
                    self._progress.item_done("Clean Filter")
                continue
            if all_plans and not metadata:
                if self._progress is not None:
                    self._progress.item_done("Clean Filter")
                continue
            items_to_delete.append(item)
            metadata_by_provider_id[item.id] = metadata
            if self._progress is not None:
                self._progress.item_done("Clean Filter")
        if self._progress is not None:
            self._progress.phase_done("Clean Filter")

        ordered_items_to_delete = self._order_items_for_deletion(
            items_to_delete,
            metadata_by_provider_id=metadata_by_provider_id,
            plan=plan,
            all_plans=all_plans,
        )

        if self._progress is not None:
            self._progress.phase_start("Clean Delete", total=len(ordered_items_to_delete))
        if not dry_run:
            remaining = list(ordered_items_to_delete)
            while remaining:
                failed: list[Item] = []
                first_error: ProviderError | None = None
                deleted_in_pass = 0
                for item in remaining:
                    try:
                        await provider.delete_item(item.id)
                        deleted_in_pass += 1
                        if self._progress is not None:
                            self._progress.item_done("Clean Delete")
                    except ProviderError as exc:
                        if first_error is None:
                            first_error = exc
                        failed.append(item)
                if not failed:
                    break
                if deleted_in_pass == 0:
                    assert first_error is not None
                    if self._progress is not None:
                        self._progress.phase_error("Clean Delete", first_error)
                    raise first_error
                remaining = failed
        if self._progress is not None:
            self._progress.phase_done("Clean Delete")

        return len(items_to_delete)

    @staticmethod
    def _item_type_rank(item_type: PlanItemType | str | None) -> int:
        return CleanDeletionPlanner.item_type_rank(item_type)

    def _order_items_for_deletion(
        self,
        items: list[Item],
        *,
        metadata_by_provider_id: dict[str, dict[str, str]],
        plan: Plan | None,
        all_plans: bool,
    ) -> list[Item]:
        return self._clean_planner.order_items_for_deletion(
            items,
            metadata_by_provider_id=metadata_by_provider_id,
            plan=plan,
            all_plans=all_plans,
        )

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

    def _persist_plan_from_remote(self, *, items: Iterable[PlanItem]) -> None:
        self._map_sync_persistence.persist_plan_from_remote(items=items, plan_paths=self._config.plan_paths)

    @staticmethod
    def _plan_type_rank(item_type: PlanItemType) -> int:
        return RemotePlanPersistence.plan_type_rank(item_type)

    def _plan_item_from_remote(self, *, item_id: str, metadata: dict[str, str], title: str, body: str) -> PlanItem:
        return self._map_sync_parser.plan_item_from_remote(item_id=item_id, metadata=metadata, title=title, body=body)

    @staticmethod
    def _resolve_remote_item_type(*, item_id: str, metadata: dict[str, str]) -> PlanItemType:
        return RemotePlanParser.resolve_remote_item_type(item_id=item_id, metadata=metadata)

    @staticmethod
    def _extract_markdown_sections(body: str) -> dict[str, str]:
        return RemotePlanParser.extract_markdown_sections(body)

    @staticmethod
    def _parse_bullets(section: str | None) -> list[str]:
        return RemotePlanParser.parse_bullets(section)
