"""Core sync pipeline engine."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

from planpilot_v2.contracts.config import PlanPilotConfig
from planpilot_v2.contracts.exceptions import CreateItemPartialFailureError, SyncError
from planpilot_v2.contracts.item import CreateItemInput, Item, ItemSearchFilters, UpdateItemInput
from planpilot_v2.contracts.plan import Plan, PlanItem, PlanItemType
from planpilot_v2.contracts.provider import Provider
from planpilot_v2.contracts.renderer import BodyRenderer, RenderContext
from planpilot_v2.contracts.sync import SyncEntry, SyncMap, SyncResult, to_sync_entry
from planpilot_v2.engine.utils import compute_parent_blocked_by, parse_metadata_block

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
    ) -> None:
        self._provider = provider
        self._renderer = renderer
        self._config = config
        self._dry_run = dry_run
        self._semaphore = asyncio.Semaphore(config.max_concurrent)

    async def sync(self, plan: Plan, plan_id: str) -> SyncResult:
        sync_map = SyncMap(plan_id=plan_id, target=self._config.target, board_url=self._config.board_url)
        items_created = {item_type: 0 for item_type in _ITEM_TYPE_ORDER}

        if self._dry_run:
            self._dry_run_upsert(plan, sync_map, items_created)
            return SyncResult(sync_map=sync_map, items_created=items_created, dry_run=True)

        existing_map = await self._discover(plan_id)
        item_objects: dict[str, Item] = {}
        for item_id, existing_item in existing_map.items():
            sync_map.entries[item_id] = to_sync_entry(existing_item)
            item_objects[item_id] = existing_item

        try:
            await self._upsert(plan, plan_id, existing_map, sync_map, item_objects, items_created)
            await self._enrich(plan, plan_id, sync_map, item_objects)
            await self._set_relations(plan, item_objects)
        except* SyncError as sync_error_group:
            first_sync_error = sync_error_group.exceptions[0]
            raise first_sync_error from None

        return SyncResult(sync_map=sync_map, items_created=items_created, dry_run=False)

    async def _discover(self, plan_id: str) -> dict[str, Item]:
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

        return existing_map

    def _dry_run_upsert(
        self,
        plan: Plan,
        sync_map: SyncMap,
        items_created: dict[PlanItemType, int],
    ) -> None:
        for item_type in _ITEM_TYPE_ORDER:
            for plan_item in self._items_by_type(plan, item_type):
                sync_map.entries[plan_item.id] = SyncEntry(
                    id=f"dry-run-{plan_item.id}",
                    key="dry-run",
                    url="dry-run",
                    item_type=plan_item.type,
                )
                items_created[item_type] += 1

    async def _upsert(
        self,
        plan: Plan,
        plan_id: str,
        existing_map: dict[str, Item],
        sync_map: SyncMap,
        item_objects: dict[str, Item],
        items_created: dict[PlanItemType, int],
    ) -> None:
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
                        )
                    )

    async def _upsert_item(
        self,
        plan_item: PlanItem,
        plan: Plan,
        plan_id: str,
        existing_map: dict[str, Item],
        sync_map: SyncMap,
        item_objects: dict[str, Item],
        items_created: dict[PlanItemType, int],
    ) -> None:
        if plan_item.id in existing_map:
            existing = existing_map[plan_item.id]
            sync_map.entries[plan_item.id] = to_sync_entry(existing)
            item_objects[plan_item.id] = existing
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

    async def _enrich(
        self,
        plan: Plan,
        plan_id: str,
        sync_map: SyncMap,
        item_objects: dict[str, Item],
    ) -> None:
        async with asyncio.TaskGroup() as tg:
            for plan_item in plan.items:
                tg.create_task(self._enrich_item(plan, plan_item, plan_id, sync_map, item_objects))

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
            return

        context = self._build_context(plan, plan_item, plan_id, sync_map)
        body = self._renderer.render(plan_item, context)
        update_input = UpdateItemInput(
            title=plan_item.title,
            body=body,
            item_type=plan_item.type,
            labels=[self._config.label],
            size=plan_item.estimate.tshirt if plan_item.estimate is not None else None,
        )

        updated_item = await self._guarded(self._provider.update_item(entry.id, update_input))
        item_objects[plan_item.id] = updated_item

    async def _set_relations(self, plan: Plan, item_objects: dict[str, Item]) -> None:
        by_id = {item.id: item for item in plan.items}
        parent_pairs: set[tuple[str, str]] = set()
        dependency_pairs: set[tuple[str, str]] = set()

        for plan_item in plan.items:
            if plan_item.id not in item_objects:
                continue
            if plan_item.parent_id and plan_item.parent_id in item_objects:
                parent_pairs.add((plan_item.id, plan_item.parent_id))
            for dep_id in plan_item.depends_on:
                if dep_id in item_objects and dep_id != plan_item.id:
                    dependency_pairs.add((plan_item.id, dep_id))

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

        async with asyncio.TaskGroup() as tg:
            for child_id, parent_id in parent_pairs:
                child = item_objects[child_id]
                parent = item_objects[parent_id]
                tg.create_task(self._guarded(child.set_parent(parent)))

            for blocked_id, blocker_id in dependency_pairs:
                blocked = item_objects[blocked_id]
                blocker = item_objects[blocker_id]
                tg.create_task(self._guarded(blocked.add_dependency(blocker)))

    def _build_context(
        self,
        plan: Plan,
        plan_item: PlanItem,
        plan_id: str,
        sync_map: SyncMap,
    ) -> RenderContext:
        parent_ref: str | None = None
        if plan_item.parent_id and plan_item.parent_id in sync_map.entries:
            parent_ref = sync_map.entries[plan_item.parent_id].key

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
