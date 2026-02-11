"""Core sync pipeline engine."""

from __future__ import annotations

import asyncio
import warnings
from collections.abc import Awaitable
from typing import TypeVar

from planpilot.contracts.config import PlanPilotConfig
from planpilot.contracts.exceptions import CreateItemPartialFailureError, ProviderError, SyncError
from planpilot.contracts.item import CreateItemInput, Item, ItemSearchFilters, UpdateItemInput
from planpilot.contracts.plan import Plan, PlanItem, PlanItemType
from planpilot.contracts.provider import Provider
from planpilot.contracts.renderer import BodyRenderer, RenderContext
from planpilot.contracts.sync import SyncMap, SyncResult, to_sync_entry
from planpilot.engine.progress import NullSyncProgress, SyncProgress
from planpilot.engine.utils import compute_parent_blocked_by, parse_metadata_block

T = TypeVar("T")
_ITEM_TYPE_ORDER = (PlanItemType.EPIC, PlanItemType.STORY, PlanItemType.TASK)


class SyncEngine:
    def __init__(
        self,
        provider: Provider,
        renderer: BodyRenderer,
        config: PlanPilotConfig,
        *,
        dry_run: bool = False,
        progress: SyncProgress | None = None,
    ) -> None:
        self._provider = provider
        self._renderer = renderer
        self._config = config
        self._dry_run = dry_run
        self._semaphore = asyncio.Semaphore(config.max_concurrent)
        self._progress: SyncProgress = progress or NullSyncProgress()

    async def sync(self, plan: Plan, plan_id: str) -> SyncResult:
        sync_map = SyncMap(plan_id=plan_id, target=self._config.target, board_url=self._config.board_url)
        items_created = {item_type: 0 for item_type in _ITEM_TYPE_ORDER}

        existing_map = await self._discover(plan_id)
        item_objects: dict[str, Item] = {}
        plan_type_by_id = {item.id: item.type for item in plan.items}
        for item_id, existing_item in existing_map.items():
            entry = to_sync_entry(existing_item)
            entry.item_type = plan_type_by_id.get(item_id, entry.item_type)
            sync_map.entries[item_id] = entry
            item_objects[item_id] = existing_item

        try:
            created_ids: set[str] = set()
            await self._upsert(plan, plan_id, existing_map, sync_map, item_objects, items_created, created_ids)
            await self._enrich(plan, plan_id, sync_map, item_objects)
            await self._set_relations(plan, item_objects, created_ids)
        except* (SyncError, ProviderError) as error_group:
            first_error = error_group.exceptions[0]
            raise first_error from error_group

        return SyncResult(sync_map=sync_map, items_created=items_created, dry_run=self._dry_run)

    async def _discover(self, plan_id: str) -> dict[str, Item]:
        self._progress.phase_start("Discover")
        try:
            filters = ItemSearchFilters(labels=[self._config.label], body_contains=f"PLAN_ID:{plan_id}")
            existing_items = await self._provider.search_items(filters)

            existing_map: dict[str, Item] = {}
            for item in existing_items:
                metadata = parse_metadata_block(item.body)
                if metadata.get("PLAN_ID") != plan_id:
                    continue
                item_id = metadata.get("ITEM_ID")
                if not item_id:
                    continue
                existing_map[item_id] = item

            self._progress.phase_done("Discover")
            return existing_map
        except BaseException as exc:
            self._progress.phase_error("Discover", exc)
            raise

    async def _upsert(
        self,
        plan: Plan,
        plan_id: str,
        existing_map: dict[str, Item],
        sync_map: SyncMap,
        item_objects: dict[str, Item],
        items_created: dict[PlanItemType, int],
        created_ids: set[str],
    ) -> None:
        self._progress.phase_start("Create", total=len(plan.items))
        try:
            for item_type in _ITEM_TYPE_ORDER:
                level_items = self._items_by_type(plan, item_type)
                async with asyncio.TaskGroup() as tg:
                    for plan_item in level_items:
                        tg.create_task(
                            self._upsert_item(
                                plan_item,
                                plan,
                                plan_id,
                                existing_map,
                                sync_map,
                                item_objects,
                                items_created,
                                created_ids,
                            )
                        )
            self._progress.phase_done("Create")
        except BaseException as exc:
            self._progress.phase_error("Create", exc)
            raise

    async def _upsert_item(
        self,
        plan_item: PlanItem,
        plan: Plan,
        plan_id: str,
        existing_map: dict[str, Item],
        sync_map: SyncMap,
        item_objects: dict[str, Item],
        items_created: dict[PlanItemType, int],
        created_ids: set[str],
    ) -> None:
        if plan_item.id in existing_map:
            existing = existing_map[plan_item.id]
            entry = to_sync_entry(existing)
            entry.item_type = plan_item.type
            sync_map.entries[plan_item.id] = entry
            item_objects[plan_item.id] = existing
            self._progress.item_done("Create")
            return

        context = self._build_context(plan, plan_item, plan_id, sync_map)
        body = self._renderer.render(plan_item, context)
        create_input = CreateItemInput(
            title=plan_item.title,
            body=body,
            item_type=plan_item.type,
            labels=[self._config.label],
            size=plan_item.estimate.tshirt if plan_item.estimate is not None else None,
        )

        try:
            created_item = await self._guarded(self._provider.create_item(create_input))
        except CreateItemPartialFailureError as exc:
            raise SyncError(f"Partial create failure for {plan_item.id}: {exc}") from exc

        sync_map.entries[plan_item.id] = to_sync_entry(created_item)
        item_objects[plan_item.id] = created_item
        items_created[plan_item.type] += 1
        created_ids.add(plan_item.id)
        self._progress.item_done("Create")

    async def _enrich(
        self,
        plan: Plan,
        plan_id: str,
        sync_map: SyncMap,
        item_objects: dict[str, Item],
    ) -> None:
        self._progress.phase_start("Enrich", total=len(plan.items))
        try:
            async with asyncio.TaskGroup() as tg:
                for plan_item in plan.items:
                    tg.create_task(self._enrich_item(plan, plan_item, plan_id, sync_map, item_objects))
            self._progress.phase_done("Enrich")
        except BaseException as exc:
            self._progress.phase_error("Enrich", exc)
            raise

    async def _enrich_item(
        self,
        plan: Plan,
        plan_item: PlanItem,
        plan_id: str,
        sync_map: SyncMap,
        item_objects: dict[str, Item],
    ) -> None:
        entry = sync_map.entries.get(plan_item.id)
        if entry is None:
            self._progress.item_done("Enrich")
            return

        context = self._build_context(plan, plan_item, plan_id, sync_map)
        body = self._renderer.render(plan_item, context)

        existing_item = item_objects.get(plan_item.id)
        if (
            existing_item is not None
            and existing_item.title == plan_item.title
            and existing_item.body.strip() == body.strip()
        ):
            self._progress.item_done("Enrich")
            return

        update_input = UpdateItemInput(
            title=plan_item.title,
            body=body,
            item_type=plan_item.type,
            labels=[self._config.label],
            size=plan_item.estimate.tshirt if plan_item.estimate is not None else None,
        )

        updated_item = await self._guarded(self._provider.update_item(entry.id, update_input))
        item_objects[plan_item.id] = updated_item
        self._progress.item_done("Enrich")

    async def _set_relations(self, plan: Plan, item_objects: dict[str, Item], created_ids: set[str]) -> None:
        by_id = {item.id: item for item in plan.items}
        plan_ids = set(by_id)
        parent_pairs: set[tuple[str, str]] = set()
        dependency_pairs: set[tuple[str, str]] = set()

        for plan_item in plan.items:
            if plan_item.id not in item_objects:
                continue
            if plan_item.parent_id:
                if plan_item.parent_id == plan_item.id:
                    self._handle_unresolved_reference(
                        source_item_id=plan_item.id,
                        reference_type="parent_id",
                        reference_id=plan_item.parent_id,
                    )
                    continue
                if plan_item.parent_id in item_objects:
                    parent_pairs.add((plan_item.id, plan_item.parent_id))
                elif plan_item.parent_id not in plan_ids:
                    self._handle_unresolved_reference(
                        source_item_id=plan_item.id,
                        reference_type="parent_id",
                        reference_id=plan_item.parent_id,
                    )
            for dep_id in plan_item.depends_on:
                if dep_id == plan_item.id:
                    continue
                if dep_id in item_objects:
                    dependency_pairs.add((plan_item.id, dep_id))
                elif dep_id not in plan_ids:
                    self._handle_unresolved_reference(
                        source_item_id=plan_item.id,
                        reference_type="depends_on",
                        reference_id=dep_id,
                    )

        story_rollups = compute_parent_blocked_by(plan.items, PlanItemType.STORY)
        for child_parent, blocker_parent in story_rollups:
            if child_parent in item_objects and blocker_parent in item_objects and child_parent != blocker_parent:
                dependency_pairs.add((child_parent, blocker_parent))

        # Story rollups can themselves imply epic-level blocked-by edges.
        for blocked_story_id, blocker_story_id in story_rollups:
            blocked_story = by_id.get(blocked_story_id)
            blocker_story = by_id.get(blocker_story_id)
            if blocked_story is None or blocker_story is None:
                continue
            if not blocked_story.parent_id or not blocker_story.parent_id:
                continue
            if blocked_story.parent_id in item_objects and blocker_story.parent_id in item_objects:
                dependency_pairs.add((blocked_story.parent_id, blocker_story.parent_id))

        for child_parent, blocker_parent in compute_parent_blocked_by(plan.items, PlanItemType.EPIC):
            if child_parent in item_objects and blocker_parent in item_objects and child_parent != blocker_parent:
                dependency_pairs.add((child_parent, blocker_parent))

        # Skip relation pairs where both sides already existed — relationships are already set.
        if created_ids:
            parent_pairs = {(c, p) for c, p in parent_pairs if c in created_ids or p in created_ids}
            dependency_pairs = {(b, k) for b, k in dependency_pairs if b in created_ids or k in created_ids}

        total_relations = len(parent_pairs) + len(dependency_pairs)
        self._progress.phase_start("Relations", total=total_relations)
        try:
            async with asyncio.TaskGroup() as tg:
                for child_id, parent_id in parent_pairs:
                    child = item_objects[child_id]
                    parent = item_objects[parent_id]
                    tg.create_task(self._set_parent_guarded(child, parent))

                for blocked_id, blocker_id in dependency_pairs:
                    blocked = item_objects[blocked_id]
                    blocker = item_objects[blocker_id]
                    tg.create_task(self._add_dependency_guarded(blocked, blocker))
            self._progress.phase_done("Relations")
        except BaseException as exc:
            self._progress.phase_error("Relations", exc)
            raise

    def _build_context(
        self,
        plan: Plan,
        plan_item: PlanItem,
        plan_id: str,
        sync_map: SyncMap,
    ) -> RenderContext:
        parent_ref: str | None = None
        plan_ids = {item.id for item in plan.items}
        if plan_item.parent_id:
            parent_entry = sync_map.entries.get(plan_item.parent_id)
            if parent_entry is not None:
                parent_ref = parent_entry.key
            elif plan_item.parent_id not in plan_ids:
                self._handle_unresolved_reference(
                    source_item_id=plan_item.id,
                    reference_type="parent_id",
                    reference_id=plan_item.parent_id,
                )

        sub_items: list[tuple[str, str]] = []
        for child in plan.items:
            if child.parent_id != plan_item.id:
                continue
            child_entry = sync_map.entries.get(child.id)
            if child_entry is None:
                continue
            sub_items.append((child_entry.key, child.title))
        sub_items = sorted(sub_items, key=lambda pair: (pair[0], pair[1]))

        dependencies: dict[str, str] = {}
        for dep_id in sorted(plan_item.depends_on):
            dep_entry = sync_map.entries.get(dep_id)
            if dep_entry is None:
                if dep_id not in plan_ids:
                    self._handle_unresolved_reference(
                        source_item_id=plan_item.id,
                        reference_type="depends_on",
                        reference_id=dep_id,
                    )
                continue
            dependencies[dep_id] = dep_entry.key

        return RenderContext(
            plan_id=plan_id,
            parent_ref=parent_ref,
            sub_items=sub_items,
            dependencies=dependencies,
        )

    @staticmethod
    def _items_by_type(plan: Plan, item_type: PlanItemType) -> list[PlanItem]:
        return [item for item in plan.items if item.type == item_type]

    async def _guarded(self, op: Awaitable[T]) -> T:
        async with self._semaphore:
            return await op

    async def _set_parent_guarded(self, child: Item, parent: Item) -> None:
        async with self._semaphore:
            await child.set_parent(parent)
        self._progress.item_done("Relations")

    async def _add_dependency_guarded(self, blocked: Item, blocker: Item) -> None:
        async with self._semaphore:
            await blocked.add_dependency(blocker)
        self._progress.item_done("Relations")

    def _handle_unresolved_reference(self, *, source_item_id: str, reference_type: str, reference_id: str) -> None:
        message = f"Unresolved {reference_type} reference '{reference_id}' on item '{source_item_id}' during sync."
        if self._config.validation_mode == "partial":
            warnings.warn(message, stacklevel=2)
            return
        raise SyncError(message)
