"""Command-line interface for PlanPilot v2."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from importlib.metadata import PackageNotFoundError, version

from planpilot_v2 import (
    AuthenticationError,
    ConfigError,
    PlanItemType,
    PlanLoadError,
    PlanPilot,
    PlanPilotConfig,
    PlanValidationError,
    ProviderError,
    SyncError,
    SyncResult,
    load_config,
)


def _package_version() -> str:
    try:
        return version("planpilot")
    except PackageNotFoundError:
        return "0.0.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="planpilot_v2")
    parser.add_argument("--version", action="version", version=f"%(prog)s {_package_version()}")

    subparsers = parser.add_subparsers(dest="command", required=True)
    sync_parser = subparsers.add_parser("sync")
    sync_parser.add_argument("--config", required=True, help="Path to planpilot.json")
    mode = sync_parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Preview mode")
    mode.add_argument("--apply", action="store_true", help="Apply mode")
    sync_parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")

    return parser


async def _run_sync(args: argparse.Namespace) -> SyncResult:
    config = load_config(args.config)
    pp = await PlanPilot.from_config(config)
    result = await pp.sync(dry_run=args.dry_run)
    print(_format_summary(result, config))
    return result


def _format_summary(result: SyncResult, config: PlanPilotConfig) -> str:
    mode = "dry-run" if result.dry_run else "apply"
    created_epics = result.items_created.get(PlanItemType.EPIC, 0)
    created_stories = result.items_created.get(PlanItemType.STORY, 0)
    created_tasks = result.items_created.get(PlanItemType.TASK, 0)

    total_by_type = {PlanItemType.EPIC: 0, PlanItemType.STORY: 0, PlanItemType.TASK: 0}
    for entry in result.sync_map.entries.values():
        if entry.item_type in total_by_type:
            total_by_type[entry.item_type] += 1

    existing_epics = total_by_type[PlanItemType.EPIC] - created_epics
    existing_stories = total_by_type[PlanItemType.STORY] - created_stories
    existing_tasks = total_by_type[PlanItemType.TASK] - created_tasks

    lines = [
        "",
        f"planpilot - sync complete ({mode})",
        "",
        f"  Plan ID:   {result.sync_map.plan_id}",
        f"  Target:    {result.sync_map.target}",
        f"  Board:     {result.sync_map.board_url}",
        "",
        f"  Created:   {created_epics} epic(s), {created_stories} story(s), {created_tasks} task(s)",
    ]

    if any(count > 0 for count in (existing_epics, existing_stories, existing_tasks)):
        lines.append(f"  Existing:  {existing_epics} epic(s), {existing_stories} story(s), {existing_tasks} task(s)")

    lines.append("")

    label_map = {
        PlanItemType.EPIC: "Epic",
        PlanItemType.STORY: "Story",
        PlanItemType.TASK: "Task",
    }
    for item_type in (PlanItemType.EPIC, PlanItemType.STORY, PlanItemType.TASK):
        for item_id in sorted(result.sync_map.entries):
            entry = result.sync_map.entries[item_id]
            if entry.item_type != item_type:
                continue
            lines.append(f"  {label_map[item_type]:<5}  {item_id:<6}  {entry.key:<6}  {entry.url}")

    lines.append("")
    sync_map_path = f"{config.sync_path}.dry-run" if result.dry_run else str(config.sync_path)
    lines.append(f"  Sync map:  {sync_map_path}")

    if result.dry_run:
        lines.append("")
        lines.append("  [dry-run] No changes were made")

    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(message)s", stream=sys.stderr)

    try:
        asyncio.run(_run_sync(args))
        return 0
    except (ConfigError, PlanLoadError, PlanValidationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except (AuthenticationError, ProviderError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4
    except SyncError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 5
    except Exception as exc:  # pragma: no cover - defensive fallback
        print(f"error: {exc}", file=sys.stderr)
        return 1
