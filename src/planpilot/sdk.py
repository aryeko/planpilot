"""SDK composition root for PlanPilot v2."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from planpilot.auth import create_token_resolver
from planpilot.contracts.config import PlanPaths, PlanPilotConfig
from planpilot.contracts.exceptions import ConfigError, PlanLoadError, ProjectURLError, ProviderError, SyncError
from planpilot.contracts.item import Item, ItemSearchFilters
from planpilot.contracts.plan import Plan, PlanItemType
from planpilot.contracts.provider import Provider
from planpilot.contracts.renderer import BodyRenderer
from planpilot.contracts.sync import CleanResult, SyncMap, SyncResult
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

    async def clean(self, *, dry_run: bool = False, all_plans: bool = False) -> CleanResult:
        """Discover and delete all issues belonging to a plan.

        Always uses the real provider for discovery so dry-run accurately
        reflects what would be deleted.

        Args:
            dry_run: If True, preview what would be deleted without making changes.
            all_plans: If True, delete all planpilot-managed issues (by label)
                regardless of plan_id.  When False, only issues matching the
                current plan's content hash are targeted.

        Returns:
            CleanResult with plan_id, items_deleted count, and dry_run flag.
        """
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
        plan: Plan,
        *,
        dry_run: bool,
        all_plans: bool = False,
    ) -> int:
        """Discover issues by label (and optionally plan_id) and delete them."""
        if all_plans:
            filters = ItemSearchFilters(labels=[self._config.label])
        else:
            filters = ItemSearchFilters(labels=[self._config.label], body_contains=f"PLAN_ID:{plan_id}")

        existing_items = await provider.search_items(filters)

        items_to_delete: list[Item] = []
        metadata_by_provider_id: dict[str, dict[str, str]] = {}
        for item in existing_items:
            metadata = parse_metadata_block(item.body)
            if not all_plans and metadata.get("PLAN_ID") != plan_id:
                continue
            # In all_plans mode, any item with a PLANPILOT metadata block qualifies
            if all_plans and not metadata:
                continue
            items_to_delete.append(item)
            metadata_by_provider_id[item.id] = metadata

        ordered_items_to_delete = self._order_items_for_deletion(
            items_to_delete,
            metadata_by_provider_id=metadata_by_provider_id,
            plan=plan,
            all_plans=all_plans,
        )

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
                    except ProviderError as exc:
                        if first_error is None:
                            first_error = exc
                        failed.append(item)
                if not failed:
                    break
                if deleted_in_pass == 0:
                    assert first_error is not None
                    raise first_error
                remaining = failed

        return len(items_to_delete)

    @staticmethod
    def _item_type_rank(item_type: PlanItemType | str | None) -> int:
        if item_type in {PlanItemType.TASK, "TASK"}:
            return 0
        if item_type in {PlanItemType.STORY, "STORY"}:
            return 1
        if item_type in {PlanItemType.EPIC, "EPIC"}:
            return 2
        return 3

    def _order_items_for_deletion(
        self,
        items: list[Item],
        *,
        metadata_by_provider_id: dict[str, dict[str, str]],
        plan: Plan,
        all_plans: bool,
    ) -> list[Item]:
        if not items:
            return []

        item_by_provider_id = {item.id: item for item in items}
        plan_items_by_id = {plan_item.id: plan_item for plan_item in plan.items}
        provider_id_by_item_id: dict[str, str] = {}
        plan_type_by_provider_id: dict[str, PlanItemType] = {}

        for item in items:
            metadata = metadata_by_provider_id.get(item.id, {})
            item_id = metadata.get("ITEM_ID")
            if not item_id:
                continue
            provider_id_by_item_id[item_id] = item.id
            plan_item = plan_items_by_id.get(item_id)
            if plan_item is not None:
                plan_type_by_provider_id[item.id] = plan_item.type

        prerequisites: dict[str, set[str]] = {item.id: set() for item in items}
        dependents: dict[str, set[str]] = {item.id: set() for item in items}

        for item in items:
            metadata = metadata_by_provider_id.get(item.id, {})
            item_id = metadata.get("ITEM_ID")
            parent_item_id: str | None = None

            if all_plans:
                parent_item_id = metadata.get("PARENT_ID")
            elif item_id:
                plan_item = plan_items_by_id.get(item_id)
                parent_item_id = plan_item.parent_id if plan_item is not None else None

            if not parent_item_id:
                continue

            parent_provider_id = provider_id_by_item_id.get(parent_item_id)
            if parent_provider_id is None or parent_provider_id == item.id:
                continue

            prerequisites[parent_provider_id].add(item.id)
            dependents[item.id].add(parent_provider_id)

        def _sort_key(provider_id: str) -> tuple[int, str, str]:
            item = item_by_provider_id[provider_id]
            metadata = metadata_by_provider_id.get(provider_id, {})
            type_hint: PlanItemType | str | None = (
                plan_type_by_provider_id.get(provider_id) or metadata.get("ITEM_TYPE") or item.item_type
            )
            return (self._item_type_rank(type_hint), item.key, item.id)

        remaining_prereqs = {provider_id: set(reqs) for provider_id, reqs in prerequisites.items()}
        ready = sorted(
            [provider_id for provider_id, reqs in remaining_prereqs.items() if not reqs],
            key=_sort_key,
        )
        ordered: list[str] = []

        while ready:
            current = ready.pop(0)
            ordered.append(current)
            for parent in sorted(dependents[current], key=_sort_key):
                prereq_set = remaining_prereqs[parent]
                if current in prereq_set:
                    prereq_set.remove(current)
                    if not prereq_set:
                        ready.append(parent)
            ready.sort(key=_sort_key)

        if len(ordered) != len(items):
            remaining = [provider_id for provider_id in item_by_provider_id if provider_id not in set(ordered)]
            ordered.extend(sorted(remaining, key=_sort_key))

        return [item_by_provider_id[provider_id] for provider_id in ordered]

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
