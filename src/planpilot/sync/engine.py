"""Sync engine orchestrating the plan-to-issues sync pipeline."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from planpilot.config import SyncConfig
from planpilot.exceptions import SyncError
from planpilot.models.plan import Epic, Plan, Story, Task
from planpilot.models.project import (
    CreateIssueInput,
    FieldValue,
    ProjectContext,
    RepoContext,
)
from planpilot.models.sync import SyncEntry, SyncMap, SyncResult
from planpilot.plan import compute_plan_id, load_plan, validate_plan
from planpilot.providers.base import Provider
from planpilot.providers.github.mapper import build_issue_mapping, resolve_option_id
from planpilot.rendering.base import BodyRenderer
from planpilot.sync.relations import compute_epic_blocked_by, compute_story_blocked_by

logger = logging.getLogger(__name__)


class SyncEngine:
    """Orchestrates the plan-to-provider sync pipeline.

    The sync runs in five phases:
    1. Setup — authenticate and resolve provider context
    2. Discovery — find existing issues for this plan
    3. Upsert — create missing issues (epics → stories → tasks)
    4. Enrich — update all bodies with cross-references
    5. Relations — set up sub-issue and blocked-by links

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

        Returns:
            SyncResult with the sync map and creation counts.
        """
        cfg = self._config
        dry_run = cfg.dry_run

        # Load and validate plan
        plan = load_plan(cfg.epics_path, cfg.stories_path, cfg.tasks_path)
        validate_plan(plan)
        plan_id = compute_plan_id(plan)

        if dry_run:
            logger.info("[dry-run] No changes will be made")

        # Phase 1: Setup
        await self._provider.check_auth()
        repo_ctx = await self._provider.get_repo_context(cfg.repo, cfg.label)
        project_ctx = await self._provider.get_project_context(cfg.project_url, cfg.field_config)

        # Phase 2: Discovery
        existing_issues = await self._provider.search_issues(cfg.repo, plan_id)
        existing_raw = [{"id": e.id, "number": e.number, "body": e.body} for e in existing_issues]
        existing_map = build_issue_mapping(existing_raw, plan_id=plan_id)

        sync_map = SyncMap(
            plan_id=plan_id,
            repo=cfg.repo,
            project_url=cfg.project_url,
        )

        counters = {"epics": 0, "stories": 0, "tasks": 0}
        story_by_id = {s.id: s for s in plan.stories}
        task_by_id = {t.id: t for t in plan.tasks}

        # Phase 3: Upsert epics
        for epic in plan.epics:
            entry = await self._upsert_epic(epic, plan_id, repo_ctx, project_ctx, existing_map, dry_run, counters)
            sync_map.epics[epic.id] = entry

        # Upsert stories
        for story in plan.stories:
            entry = await self._upsert_story(
                story, plan_id, repo_ctx, project_ctx, existing_map, sync_map, dry_run, counters
            )
            sync_map.stories[story.id] = entry

        # Upsert tasks
        for task in plan.tasks:
            entry = await self._upsert_task(
                task, plan_id, repo_ctx, project_ctx, existing_map, sync_map, dry_run, counters
            )
            sync_map.tasks[task.id] = entry

        # Phase 4: Enrich bodies
        if not dry_run:
            await self._enrich_bodies(plan, plan_id, sync_map, task_by_id, story_by_id)

        # Phase 5: Relations
        if not dry_run:
            await self._set_relations(plan, sync_map)

        # Write sync map
        Path(cfg.sync_path).write_text(sync_map.model_dump_json(indent=2), encoding="utf-8")

        return SyncResult(
            sync_map=sync_map,
            epics_created=counters["epics"],
            stories_created=counters["stories"],
            tasks_created=counters["tasks"],
            dry_run=dry_run,
        )

    async def _upsert_epic(
        self,
        epic: Epic,
        plan_id: str,
        repo_ctx: RepoContext,
        project_ctx: ProjectContext | None,
        existing_map: dict[str, dict[str, dict[str, Any]]],
        dry_run: bool,
        counters: dict[str, int],
    ) -> SyncEntry:
        """Create or find an epic issue."""
        existing = existing_map["epics"].get(epic.id)
        if existing:
            return SyncEntry(
                issue_number=existing["number"],
                url=f"https://github.com/{self._config.repo}/issues/{existing['number']}",
                node_id=existing["id"],
            )

        body = self._renderer.render_epic(epic, plan_id)
        if dry_run:
            logger.info("[dry-run] create epic: %s", epic.title)
            counters["epics"] += 1
            return SyncEntry(issue_number=0, url="dry-run", node_id=f"dry-run-epic-{epic.id}")

        ref = await self._provider.create_issue(
            CreateIssueInput(
                repo_id=repo_ctx.repo_id or "",
                title=epic.title,
                body=body,
                label_ids=[repo_ctx.label_id] if repo_ctx.label_id else [],
            )
        )
        counters["epics"] += 1

        # Set issue type
        type_id = repo_ctx.issue_type_ids.get("Epic")
        if type_id:
            await self._provider.set_issue_type(ref.id, type_id)

        # Add to project
        item_id = None
        if project_ctx:
            item_id = await self._provider.add_to_project(project_ctx.project_id, ref.id)
            if item_id:
                await self._set_project_fields(project_ctx, item_id)

        return SyncEntry(issue_number=ref.number, url=ref.url, node_id=ref.id, project_item_id=item_id)

    async def _upsert_story(
        self,
        story: Story,
        plan_id: str,
        repo_ctx: RepoContext,
        project_ctx: ProjectContext | None,
        existing_map: dict[str, dict[str, dict[str, Any]]],
        sync_map: SyncMap,
        dry_run: bool,
        counters: dict[str, int],
    ) -> SyncEntry:
        """Create or find a story issue."""
        existing = existing_map["stories"].get(story.id)
        if existing:
            return SyncEntry(
                issue_number=existing["number"],
                url=f"https://github.com/{self._config.repo}/issues/{existing['number']}",
                node_id=existing["id"],
            )

        epic_num = sync_map.epics[story.epic_id].issue_number
        epic_ref = f"#{epic_num}"
        body = self._renderer.render_story(story, plan_id, epic_ref)

        if dry_run:
            logger.info("[dry-run] create story: %s", story.title)
            counters["stories"] += 1
            return SyncEntry(issue_number=0, url="dry-run", node_id=f"dry-run-story-{story.id}")

        ref = await self._provider.create_issue(
            CreateIssueInput(
                repo_id=repo_ctx.repo_id or "",
                title=story.title,
                body=body,
                label_ids=[repo_ctx.label_id] if repo_ctx.label_id else [],
            )
        )
        counters["stories"] += 1

        type_id = repo_ctx.issue_type_ids.get("Story")
        if type_id:
            await self._provider.set_issue_type(ref.id, type_id)

        item_id = None
        if project_ctx:
            item_id = await self._provider.add_to_project(project_ctx.project_id, ref.id)
            if item_id:
                await self._set_project_fields(project_ctx, item_id)

        return SyncEntry(issue_number=ref.number, url=ref.url, node_id=ref.id, project_item_id=item_id)

    async def _upsert_task(
        self,
        task: Task,
        plan_id: str,
        repo_ctx: RepoContext,
        project_ctx: ProjectContext | None,
        existing_map: dict[str, dict[str, dict[str, Any]]],
        sync_map: SyncMap,
        dry_run: bool,
        counters: dict[str, int],
    ) -> SyncEntry:
        """Create or find a task issue."""
        existing = existing_map["tasks"].get(task.id)
        if existing:
            return SyncEntry(
                issue_number=existing["number"],
                url=f"https://github.com/{self._config.repo}/issues/{existing['number']}",
                node_id=existing["id"],
            )

        story_num = sync_map.stories[task.story_id].issue_number
        story_ref = f"#{story_num}"
        placeholder_deps = "Blocked by:\n\n* (populated after mapping exists)"
        body = self._renderer.render_task(task, plan_id, story_ref, placeholder_deps)

        if dry_run:
            logger.info("[dry-run] create task: %s", task.title)
            counters["tasks"] += 1
            return SyncEntry(issue_number=0, url="dry-run", node_id=f"dry-run-task-{task.id}")

        ref = await self._provider.create_issue(
            CreateIssueInput(
                repo_id=repo_ctx.repo_id or "",
                title=task.title,
                body=body,
                label_ids=[repo_ctx.label_id] if repo_ctx.label_id else [],
            )
        )
        counters["tasks"] += 1

        type_id = repo_ctx.issue_type_ids.get("Task")
        if type_id:
            await self._provider.set_issue_type(ref.id, type_id)

        item_id = None
        if project_ctx:
            item_id = await self._provider.add_to_project(project_ctx.project_id, ref.id)
            if item_id:
                size_option_id = None
                if self._config.field_config.size_from_tshirt and project_ctx.size_field_id:
                    tshirt = task.estimate.tshirt if task.estimate else None
                    size_option_id = resolve_option_id(project_ctx.size_options, tshirt)
                await self._set_project_fields(project_ctx, item_id, size_option_id=size_option_id)

        return SyncEntry(issue_number=ref.number, url=ref.url, node_id=ref.id, project_item_id=item_id)

    async def _set_project_fields(
        self,
        project_ctx: ProjectContext,
        item_id: str,
        size_option_id: str | None = None,
    ) -> None:
        """Set standard project fields on an item."""
        pid = project_ctx.project_id
        if project_ctx.status_field:
            await self._provider.set_project_field(
                pid, item_id, project_ctx.status_field.field_id, project_ctx.status_field.value
            )
        if project_ctx.priority_field:
            await self._provider.set_project_field(
                pid, item_id, project_ctx.priority_field.field_id, project_ctx.priority_field.value
            )
        if project_ctx.iteration_field:
            await self._provider.set_project_field(
                pid, item_id, project_ctx.iteration_field.field_id, project_ctx.iteration_field.value
            )
        if project_ctx.size_field_id and size_option_id:
            await self._provider.set_project_field(
                pid, item_id, project_ctx.size_field_id, FieldValue(single_select_option_id=size_option_id)
            )

    async def _enrich_bodies(
        self,
        plan: Plan,
        plan_id: str,
        sync_map: SyncMap,
        task_by_id: dict[str, Task],
        story_by_id: dict[str, Story],
    ) -> None:
        """Phase 4: Update all bodies with cross-references."""
        repo = self._config.repo

        # Update task bodies with dependencies
        for task in plan.tasks:
            story_num = sync_map.stories[task.story_id].issue_number
            deps = {dep: f"#{sync_map.tasks[dep].issue_number}" for dep in task.depends_on}
            deps_block = self._renderer.render_deps_block(deps)
            body = self._renderer.render_task(task, plan_id, f"#{story_num}", deps_block)
            entry = sync_map.tasks[task.id]
            await self._provider.update_issue(repo, entry.issue_number, task.title, body)

        # Update story bodies with task checklists
        for story in plan.stories:
            epic_num = sync_map.epics[story.epic_id].issue_number
            task_items = []
            for tid in story.task_ids:
                tentry = sync_map.tasks.get(tid)
                if tentry:
                    task_items.append((tentry.issue_number, task_by_id[tid].title))
            tasks_list = self._renderer.render_checklist(task_items)
            body = self._renderer.render_story(story, plan_id, f"#{epic_num}", tasks_list)
            entry = sync_map.stories[story.id]
            await self._provider.update_issue(repo, entry.issue_number, story.title, body)

        # Update epic bodies with story checklists
        for epic in plan.epics:
            story_items = []
            for sid in epic.story_ids:
                sentry = sync_map.stories.get(sid)
                if sentry:
                    story_items.append((sentry.issue_number, story_by_id[sid].title))
            stories_list = self._renderer.render_checklist(story_items)
            body = self._renderer.render_epic(epic, plan_id, stories_list)
            entry = sync_map.epics[epic.id]
            await self._provider.update_issue(repo, entry.issue_number, epic.title, body)

    async def _set_relations(
        self,
        plan: Plan,
        sync_map: SyncMap,
    ) -> None:
        """Phase 5: Set up sub-issue and blocked-by relationships."""
        all_ids = (
            [e.node_id for e in sync_map.tasks.values()]
            + [e.node_id for e in sync_map.stories.values()]
            + [e.node_id for e in sync_map.epics.values()]
        )
        relation_map = await self._provider.get_issue_relations(all_ids)

        # Task blocked-by
        for task in plan.tasks:
            task_node = sync_map.tasks[task.id].node_id
            for dep in task.depends_on:
                dep_node = sync_map.tasks[dep].node_id
                if dep_node not in relation_map.blocked_by.get(task_node, set()):
                    await self._provider.add_blocked_by(task_node, dep_node)

        # Story blocked-by (roll-up)
        story_blocked = compute_story_blocked_by(plan.tasks)
        for story_id, blocked_by_id in sorted(story_blocked):
            snode = sync_map.stories[story_id].node_id
            bnode = sync_map.stories[blocked_by_id].node_id
            if bnode not in relation_map.blocked_by.get(snode, set()):
                await self._provider.add_blocked_by(snode, bnode)

        # Epic blocked-by (roll-up)
        story_epic = {s.id: s.epic_id for s in plan.stories}
        epic_blocked = compute_epic_blocked_by(story_blocked, story_epic)
        for epic_id, blocked_by_id in sorted(epic_blocked):
            enode = sync_map.epics[epic_id].node_id
            bnode = sync_map.epics[blocked_by_id].node_id
            if bnode not in relation_map.blocked_by.get(enode, set()):
                await self._provider.add_blocked_by(enode, bnode)

        # Sub-issues: stories under epics
        for story in plan.stories:
            epic_node = sync_map.epics[story.epic_id].node_id
            story_node = sync_map.stories[story.id].node_id
            parent = relation_map.parents.get(story_node)
            if parent == epic_node:
                continue
            if parent is not None and parent != epic_node:
                raise SyncError(f"Sub-issue parent mismatch for story {story.id}")
            await self._provider.add_sub_issue(epic_node, story_node)

        # Sub-issues: tasks under stories
        for task in plan.tasks:
            story_node = sync_map.stories[task.story_id].node_id
            task_node = sync_map.tasks[task.id].node_id
            parent = relation_map.parents.get(task_node)
            if parent == story_node:
                continue
            if parent is not None and parent != story_node:
                raise SyncError(f"Sub-issue parent mismatch for task {task.id}")
            await self._provider.add_sub_issue(story_node, task_node)
