from __future__ import annotations

import logging
from collections.abc import Sequence
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING

from planpilot.config import SyncConfig
from planpilot.exceptions import SyncError
from planpilot.models.item import CreateItemInput, ItemFields, ItemType, UpdateItemInput
from planpilot.models.plan import Epic, Plan, Story, Task
from planpilot.models.sync import SyncEntry, SyncMap, SyncResult
from planpilot.plan import compute_plan_id, load_plan, validate_plan
from planpilot.providers.github.mapper import parse_markers
from planpilot.rendering.base import BodyRenderer
from planpilot.sync.relations import compute_epic_blocked_by, compute_story_blocked_by

if TYPE_CHECKING:
    from planpilot.providers.base import Provider
    from planpilot.models.item import Item

logger = logging.getLogger(__name__)


def _get_sync_entry(sync_map: dict[str, SyncEntry], entity_id: str, entity_type: str) -> SyncEntry:
    """Guard a sync_map lookup and raise descriptive SyncError on miss.

    Args:
        sync_map: Dictionary of entity IDs to SyncEntry objects.
        entity_id: The entity ID to look up.
        entity_type: Human-readable type name (e.g., "task", "story", "epic").

    Returns:
        The SyncEntry if found.

    Raises:
        SyncError: If entity_id is not in sync_map.
    """
    try:
        return sync_map[entity_id]
    except KeyError:
        raise SyncError(f"Missing {entity_type} in sync map: {entity_id!r}") from None


class SyncEngine:
    """Orchestrates the plan-to-provider sync pipeline.

    The sync runs in five phases:
    1. Setup — authenticate and resolve provider context
    2. Discovery — find existing items for this plan
    3. Upsert — create missing items (epics → stories → tasks)
    4. Enrich — update all bodies with cross-references
    5. Relations — set up sub-item and blocked-by links

    Args:
        provider: The provider adapter to use.
        renderer: The body renderer to use.
        config: Sync configuration.
    """

    def __init__(
        self,
        provider: Provider,
        renderer: BodyRenderer,
        config: SyncConfig,
    ) -> None:
        self._provider = provider
        self._renderer = renderer
        self._config = config

    async def sync(self) -> SyncResult:
        """Run the full sync pipeline.

        In dry-run mode the engine works entirely offline: it loads,
        validates, and enumerates what *would* be created without making
        any API calls.

        Returns:
            SyncResult with the sync map and creation counts.
        """
        cfg = self._config
        dry_run = cfg.dry_run

        # Load and validate plan (always local, no API)
        plan = load_plan(cfg.epics_path, cfg.stories_path, cfg.tasks_path)
        validate_plan(plan)
        plan_id = compute_plan_id(plan)

        if dry_run:
            return self._dry_run(plan, plan_id, cfg)

        return await self._apply(plan, plan_id, cfg)

    # ------------------------------------------------------------------
    # Dry-run: fully offline preview
    # ------------------------------------------------------------------

    def _dry_run(self, plan: Plan, plan_id: str, cfg: SyncConfig) -> SyncResult:
        """Preview what would be created without any API calls.

        Args:
            plan: Validated plan.
            plan_id: Deterministic plan hash.
            cfg: Sync configuration.

        Returns:
            SyncResult with placeholder entries and creation counts.
        """
        logger.info("[dry-run] No changes will be made")

        sync_map = SyncMap(
            plan_id=plan_id,
            target=cfg.target,
            board_url=cfg.board_url,
        )

        counters = {"epics": 0, "stories": 0, "tasks": 0}

        for epic in plan.epics:
            logger.info("[dry-run] create epic: %s", epic.title)
            sync_map.epics[epic.id] = SyncEntry(key="dry-run", url="dry-run", id=f"dry-run-epic-{epic.id}")
            counters["epics"] += 1

        for story in plan.stories:
            logger.info("[dry-run] create story: %s", story.title)
            sync_map.stories[story.id] = SyncEntry(key="dry-run", url="dry-run", id=f"dry-run-story-{story.id}")
            counters["stories"] += 1

        for task in plan.tasks:
            logger.info("[dry-run] create task: %s", task.title)
            sync_map.tasks[task.id] = SyncEntry(key="dry-run", url="dry-run", id=f"dry-run-task-{task.id}")
            counters["tasks"] += 1

        Path(cfg.sync_path).write_text(sync_map.model_dump_json(indent=2), encoding="utf-8")

        return SyncResult(
            sync_map=sync_map,
            epics_created=counters["epics"],
            stories_created=counters["stories"],
            tasks_created=counters["tasks"],
            dry_run=True,
        )

    # ------------------------------------------------------------------
    # Apply: full sync with API calls
    # ------------------------------------------------------------------

    async def _apply(self, plan: Plan, plan_id: str, cfg: SyncConfig) -> SyncResult:
        """Run the full sync pipeline with real API calls.

        Args:
            plan: Validated plan.
            plan_id: Deterministic plan hash.
            cfg: Sync configuration.

        Returns:
            SyncResult with the sync map and creation counts.
        """
        # Phase 0: Enter provider context manager (handles setup internally)
        async with self._provider:
            # Phase 1: Discovery
            existing_items = await self._provider.search_items(
                ItemFields(labels=[cfg.label])
            )
            existing_map = self._build_existing_map(existing_items, plan_id)

            sync_map = SyncMap(
                plan_id=plan_id,
                target=cfg.target,
                board_url=cfg.board_url,
            )

            counters = {"epics": 0, "stories": 0, "tasks": 0}
            story_by_id = {s.id: s for s in plan.stories}
            task_by_id = {t.id: t for t in plan.tasks}
            
            # Keep Item objects for relation setup
            items_by_id: dict[str, Item | None] = {}

            # Phase 2: Upsert epics
            for epic in plan.epics:
                entry, item = await self._upsert_epic(epic, plan_id, existing_map, counters)
                sync_map.epics[epic.id] = entry
                items_by_id[epic.id] = item

            # Upsert stories
            for story in plan.stories:
                entry, item = await self._upsert_story(story, plan_id, existing_map, sync_map, counters)
                sync_map.stories[story.id] = entry
                items_by_id[story.id] = item

            # Upsert tasks
            for task in plan.tasks:
                entry, item = await self._upsert_task(task, plan_id, existing_map, sync_map, counters)
                sync_map.tasks[task.id] = entry
                items_by_id[task.id] = item

            # Phase 3: Enrich bodies
            await self._enrich_bodies(plan, plan_id, sync_map, task_by_id, story_by_id)

            # Phase 4: Relations
            await self._set_relations(plan, sync_map, items_by_id)

            # Write sync map
            Path(cfg.sync_path).write_text(sync_map.model_dump_json(indent=2), encoding="utf-8")

            return SyncResult(
                sync_map=sync_map,
                epics_created=counters["epics"],
                stories_created=counters["stories"],
                tasks_created=counters["tasks"],
                dry_run=False,
            )

    def _build_existing_map(
        self,
        existing_items: Sequence[Item],
        plan_id: str,
    ) -> dict[str, dict[str, dict[str, str]]]:
        """Build a mapping of entity IDs to item metadata, filtered by plan_id.

        Parses body markers to extract plan_id and entity IDs.

        Args:
            existing_items: Raw item instances from search.
            plan_id: Only include items matching this plan_id.

        Returns:
            Nested dict: {"epics": {id: {...}}, "stories": {...}, "tasks": {...}}.
        """
        result: dict[str, dict[str, dict[str, str]]] = {"epics": {}, "stories": {}, "tasks": {}}

        for item in existing_items:
            # Extract item data (assuming Item-like interface)
            item_id = item.id
            item_key = item.key
            item_url = item.url
            item_body = item.body

            # Parse markers from body
            markers = parse_markers(item_body)
            if markers.get("plan_id") != plan_id:
                continue

            # Determine entity type from markers
            epic_id = markers.get("epic_id", "")
            story_id = markers.get("story_id", "")
            task_id = markers.get("task_id", "")

            if epic_id:
                result["epics"][epic_id] = {"id": item_id, "key": item_key, "url": item_url}
            elif story_id:
                result["stories"][story_id] = {"id": item_id, "key": item_key, "url": item_url}
            elif task_id:
                result["tasks"][task_id] = {"id": item_id, "key": item_key, "url": item_url}

        return result

    async def _upsert_epic(
        self,
        epic: Epic,
        plan_id: str,
        existing_map: dict[str, dict[str, dict[str, str]]],
        counters: dict[str, int],
    ) -> tuple[SyncEntry, Item | None]:
        """Create or find an epic item."""
        existing = existing_map["epics"].get(epic.id)
        if existing:
            return (
                SyncEntry(id=existing["id"], key=existing["key"], url=existing["url"]),
                None,
            )

        body = self._renderer.render_epic(epic, plan_id)
        item = await self._provider.create_item(
            CreateItemInput(
                title=epic.title,
                body=body,
                item_type=ItemType.EPIC,
                labels=[self._config.label],
            )
        )
        counters["epics"] += 1

        return item.to_sync_entry(), item

    async def _upsert_story(
        self,
        story: Story,
        plan_id: str,
        existing_map: dict[str, dict[str, dict[str, str]]],
        sync_map: SyncMap,
        counters: dict[str, int],
    ) -> tuple[SyncEntry, Item | None]:
        """Create or find a story item."""
        existing = existing_map["stories"].get(story.id)
        if existing:
            return (
                SyncEntry(id=existing["id"], key=existing["key"], url=existing["url"]),
                None,
            )

        epic_entry = _get_sync_entry(sync_map.epics, story.epic_id, "epic")
        epic_ref = epic_entry.key
        body = self._renderer.render_story(story, plan_id, epic_ref)
        item = await self._provider.create_item(
            CreateItemInput(
                title=story.title,
                body=body,
                item_type=ItemType.STORY,
                labels=[self._config.label],
            )
        )
        counters["stories"] += 1

        return item.to_sync_entry(), item

    async def _upsert_task(
        self,
        task: Task,
        plan_id: str,
        existing_map: dict[str, dict[str, dict[str, str]]],
        sync_map: SyncMap,
        counters: dict[str, int],
    ) -> tuple[SyncEntry, Item | None]:
        """Create or find a task item."""
        existing = existing_map["tasks"].get(task.id)
        if existing:
            return (
                SyncEntry(id=existing["id"], key=existing["key"], url=existing["url"]),
                None,
            )

        story_entry = _get_sync_entry(sync_map.stories, task.story_id, "story")
        story_ref = story_entry.key
        placeholder_deps = "Blocked by:\n\n* (populated after mapping exists)"
        body = self._renderer.render_task(task, plan_id, story_ref, placeholder_deps)
        item = await self._provider.create_item(
            CreateItemInput(
                title=task.title,
                body=body,
                item_type=ItemType.TASK,
                labels=[self._config.label],
                size=task.estimate.tshirt if task.estimate else None,
            )
        )
        counters["tasks"] += 1

        return item.to_sync_entry(), item

    async def _enrich_bodies(
        self,
        plan: Plan,
        plan_id: str,
        sync_map: SyncMap,
        task_by_id: dict[str, Task],
        story_by_id: dict[str, Story],
    ) -> None:
        """Phase 3: Update all bodies with cross-references."""
        # Update task bodies with dependencies
        for task in plan.tasks:
            story_entry = _get_sync_entry(sync_map.stories, task.story_id, "story")
            story_ref = story_entry.key
            deps = {dep: _get_sync_entry(sync_map.tasks, dep, "task").key for dep in task.depends_on}
            deps_block = self._renderer.render_deps_block(deps)
            body = self._renderer.render_task(task, plan_id, story_ref, deps_block)
            entry = _get_sync_entry(sync_map.tasks, task.id, "task")
            await self._provider.update_item(
                entry.id,
                UpdateItemInput(body=body),
            )

        # Update story bodies with task checklists
        for story in plan.stories:
            epic_entry = _get_sync_entry(sync_map.epics, story.epic_id, "epic")
            epic_ref = epic_entry.key
            task_items = []
            for tid in story.task_ids:
                tentry = sync_map.tasks.get(tid)
                if tentry:
                    task_items.append((tentry.key, task_by_id[tid].title))
            tasks_list = self._renderer.render_checklist(task_items)
            body = self._renderer.render_story(story, plan_id, epic_ref, tasks_list)
            entry = _get_sync_entry(sync_map.stories, story.id, "story")
            await self._provider.update_item(
                entry.id,
                UpdateItemInput(body=body),
            )

        # Update epic bodies with story checklists
        for epic in plan.epics:
            story_items = []
            for sid in epic.story_ids:
                sentry = sync_map.stories.get(sid)
                if sentry:
                    story_items.append((sentry.key, story_by_id[sid].title))
            stories_list = self._renderer.render_checklist(story_items)
            body = self._renderer.render_epic(epic, plan_id, stories_list)
            entry = _get_sync_entry(sync_map.epics, epic.id, "epic")
            await self._provider.update_item(
                entry.id,
                UpdateItemInput(body=body),
            )

    async def _set_relations(
        self,
        plan: Plan,
        sync_map: SyncMap,
        items_by_id: dict[str, Item | None],
    ) -> None:
        """Phase 4: Set up parent and blocked-by relationships.

        Uses Item methods which handle idempotency internally.
        """
        # Task blocked-by
        for task in plan.tasks:
            task_item = items_by_id.get(task.id)
            if not task_item:
                continue
            for dep in task.depends_on:
                dep_item = items_by_id.get(dep)
                if dep_item:
                    await task_item.add_dependency(dep_item)

        # Story blocked-by (roll-up)
        story_blocked = compute_story_blocked_by(plan.tasks)
        for story_id, blocked_by_id in sorted(story_blocked):
            story_item = items_by_id.get(story_id)
            blocker_item = items_by_id.get(blocked_by_id)
            if story_item and blocker_item:
                await story_item.add_dependency(blocker_item)

        # Epic blocked-by (roll-up)
        story_epic = {s.id: s.epic_id for s in plan.stories}
        epic_blocked = compute_epic_blocked_by(story_blocked, story_epic)
        for epic_id, blocked_by_id in sorted(epic_blocked):
            epic_item = items_by_id.get(epic_id)
            blocker_item = items_by_id.get(blocked_by_id)
            if epic_item and blocker_item:
                await epic_item.add_dependency(blocker_item)

        # Sub-items: stories under epics
        for story in plan.stories:
            epic_item = items_by_id.get(story.epic_id)
            story_item = items_by_id.get(story.id)
            if story_item and epic_item:
                await story_item.set_parent(epic_item)

        # Sub-items: tasks under stories
        for task in plan.tasks:
            story_item = items_by_id.get(task.story_id)
            task_item = items_by_id.get(task.id)
            if task_item and story_item:
                await task_item.set_parent(story_item)
