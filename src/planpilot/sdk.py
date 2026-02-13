"""SDK composition root for PlanPilot v2."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from planpilot.auth import create_token_resolver
from planpilot.clean import CleanDeletionPlanner
from planpilot.config.loader import load_config as _load_config
from planpilot.contracts.config import PlanPaths, PlanPilotConfig
from planpilot.contracts.exceptions import ConfigError, PlanLoadError
from planpilot.contracts.item import Item
from planpilot.contracts.plan import Plan, PlanItem, PlanItemType
from planpilot.contracts.provider import Provider
from planpilot.contracts.renderer import BodyRenderer
from planpilot.contracts.sync import CleanResult, MapSyncResult, SyncMap, SyncResult
from planpilot.engine.progress import SyncProgress
from planpilot.map_sync import MapSyncReconciler, RemotePlanParser, RemotePlanPersistence
from planpilot.plan import PlanHasher as PlanHasher
from planpilot.plan import PlanLoader
from planpilot.providers.factory import create_provider
from planpilot.renderers import create_renderer
from planpilot.sdk_ops.clean_ops import discover_and_delete_items as discover_and_delete_items_op
from planpilot.sdk_ops.clean_ops import run_clean as run_clean_op
from planpilot.sdk_ops.map_sync_ops import discover_remote_plan_ids as discover_remote_plan_ids_op
from planpilot.sdk_ops.map_sync_ops import persist_plan_from_remote as persist_plan_from_remote_op
from planpilot.sdk_ops.map_sync_ops import run_map_sync as run_map_sync_op
from planpilot.sdk_ops.persistence import load_sync_map as load_sync_map_op
from planpilot.sdk_ops.persistence import output_sync_path as output_sync_path_op
from planpilot.sdk_ops.persistence import persist_sync_map as persist_sync_map_op
from planpilot.sdk_ops.sync_ops import run_sync as run_sync_op


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
        return await run_sync_op(self, plan, dry_run=dry_run)

    async def discover_remote_plan_ids(self) -> list[str]:
        """Discover unique PLAN_ID values from provider metadata."""
        return await discover_remote_plan_ids_op(self)

    async def map_sync(self, *, plan_id: str, dry_run: bool = False) -> MapSyncResult:
        """Reconcile local sync-map and bootstrap local plan from remote discovery."""
        return await run_map_sync_op(self, plan_id=plan_id, dry_run=dry_run)

    async def clean(self, *, dry_run: bool = False, all_plans: bool = False) -> CleanResult:
        """Discover and delete all issues belonging to a plan.

        Always uses the real provider for discovery so dry-run accurately
        reflects what would be deleted.
        """
        return await run_clean_op(self, dry_run=dry_run, all_plans=all_plans)

    async def _discover_and_delete_items(
        self,
        provider: Provider,
        plan_id: str,
        plan: Plan | None,
        *,
        dry_run: bool,
        all_plans: bool = False,
    ) -> int:
        return await discover_and_delete_items_op(
            self,
            provider,
            plan_id,
            plan,
            dry_run=dry_run,
            all_plans=all_plans,
        )

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
        persist_sync_map_op(config=self._config, sync_map=sync_map, dry_run=dry_run)

    def _output_sync_path(self, *, dry_run: bool) -> Path:
        return output_sync_path_op(config=self._config, dry_run=dry_run)

    def _load_sync_map(self, *, plan_id: str) -> SyncMap:
        return load_sync_map_op(config=self._config, plan_id=plan_id)

    def _persist_plan_from_remote(self, *, items: Iterable[PlanItem]) -> None:
        persist_plan_from_remote_op(self, items=items)

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
