"""Sync command formatting."""

from __future__ import annotations

import argparse

from planpilot import PlanItemType, PlanPilotConfig, SyncResult
from planpilot.cli.common import format_type_breakdown
from planpilot.cli.persistence.sync_map import persist_sync_map
from planpilot.cli.progress.rich import RichSyncProgress


def format_sync_summary(result: SyncResult, config: PlanPilotConfig) -> str:
    mode = "dry-run" if result.dry_run else "apply"
    created_epics = result.items_created.get(PlanItemType.EPIC, 0)
    created_stories = result.items_created.get(PlanItemType.STORY, 0)
    created_tasks = result.items_created.get(PlanItemType.TASK, 0)
    total_created = created_epics + created_stories + created_tasks

    total_by_type = {PlanItemType.EPIC: 0, PlanItemType.STORY: 0, PlanItemType.TASK: 0}
    for entry in result.sync_map.entries.values():
        item_type = entry.item_type
        if item_type is not None and item_type in total_by_type:
            total_by_type[item_type] += 1

    total_items = len(result.sync_map.entries)
    total_matched = total_items - total_created

    matched_epics = total_by_type[PlanItemType.EPIC] - created_epics
    matched_stories = total_by_type[PlanItemType.STORY] - created_stories
    matched_tasks = total_by_type[PlanItemType.TASK] - created_tasks

    lines = [
        "",
        f"planpilot - sync complete ({mode})",
        "",
        f"  Plan ID:   {result.sync_map.plan_id}",
        f"  Target:    {result.sync_map.target}",
        f"  Board:     {result.sync_map.board_url}",
        "",
        "  Items:     {} total ({})".format(
            total_items,
            format_type_breakdown(
                epics=total_by_type[PlanItemType.EPIC],
                stories=total_by_type[PlanItemType.STORY],
                tasks=total_by_type[PlanItemType.TASK],
            ),
        ),
    ]

    if total_created > 0:
        created_breakdown = format_type_breakdown(
            epics=created_epics,
            stories=created_stories,
            tasks=created_tasks,
        )
        lines.append(f"  Created:   {total_created} ({created_breakdown})")
    if total_matched > 0:
        matched_breakdown = format_type_breakdown(
            epics=matched_epics,
            stories=matched_stories,
            tasks=matched_tasks,
        )
        lines.append(f"  Matched:   {total_matched} ({matched_breakdown})")
    if total_created == 0:
        lines.append("  Status:    all items up to date")

    lines.append("")
    sync_map_path = f"{config.sync_path}.dry-run" if result.dry_run else str(config.sync_path)
    lines.append(f"  Sync map:  {sync_map_path}")

    if result.dry_run:
        lines.append("")
        lines.append("  [dry-run] No changes were made")

    lines.append("")
    return "\n".join(lines)


async def run_sync(args: argparse.Namespace) -> SyncResult:
    import planpilot.cli as cli

    config = cli.load_config(args.config)

    if not args.verbose:
        with RichSyncProgress() as progress:
            pp = await cli.PlanPilot.from_config(config, progress=progress)
            result = await pp.sync(dry_run=args.dry_run)
    else:
        pp = await cli.PlanPilot.from_config(config)
        result = await pp.sync(dry_run=args.dry_run)

    persist_sync_map(sync_map=result.sync_map, sync_path=config.sync_path, dry_run=args.dry_run)

    print(cli._format_summary(result, config))
    return result


__all__ = ["format_sync_summary", "run_sync"]
