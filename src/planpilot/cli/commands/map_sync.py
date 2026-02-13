"""Map-sync command formatting."""

from __future__ import annotations

import argparse
import sys

from planpilot import MapSyncResult, PlanPilotConfig
from planpilot.cli.common import format_comma_or_none
from planpilot.persistence.remote_plan import persist_plan_from_remote
from planpilot.persistence.sync_map import persist_sync_map


def format_map_sync_summary(result: MapSyncResult, config: PlanPilotConfig) -> str:
    mode = "dry-run" if result.dry_run else "apply"

    lines = [
        "",
        f"planpilot - map sync complete ({mode})",
        "",
        f"  Plan ID:      {result.sync_map.plan_id}",
        f"  Candidates:   {len(result.candidate_plan_ids)} discovered",
        f"  Target:       {result.sync_map.target}",
        f"  Board:        {result.sync_map.board_url}",
        "",
        f"  Plan items:   {result.plan_items_synced}",
        f"  Entries:      {len(result.sync_map.entries)}",
        f"  Added:        {len(result.added)} ({format_comma_or_none(result.added)})",
        f"  Updated:      {len(result.updated)} ({format_comma_or_none(result.updated)})",
        f"  Removed:      {len(result.removed)} ({format_comma_or_none(result.removed)})",
        "",
        f"  Sync map:     {config.sync_path}",
    ]
    if result.dry_run:
        lines.append("")
        lines.append("  [dry-run] No changes were made")
    lines.append("")
    return "\n".join(lines)


def resolve_selected_plan_id(*, explicit_plan_id: str | None, candidate_plan_ids: list[str]) -> str:
    import planpilot.cli as cli

    if explicit_plan_id is not None and explicit_plan_id.strip():
        return explicit_plan_id.strip()

    if not candidate_plan_ids:
        raise cli.ConfigError(
            "No remote PLAN_ID values were discovered; run sync first or pass --plan-id to target a known plan ID"
        )
    if len(candidate_plan_ids) == 1:
        return candidate_plan_ids[0]
    if not sys.stdin.isatty():
        raise cli.ConfigError("Multiple remote PLAN_ID values found; rerun with --plan-id in non-interactive mode")

    try:
        import questionary
    except ImportError as exc:  # pragma: no cover
        raise cli.ConfigError(
            "questionary is required for interactive plan-id selection (install questionary or pass --plan-id)"
        ) from exc

    selected = questionary.select("Select remote PLAN_ID to reconcile:", choices=candidate_plan_ids).ask()
    if selected is None:
        raise cli.ConfigError("Aborted plan-id selection")
    return str(selected)


async def run_map_sync(args: argparse.Namespace) -> MapSyncResult:
    import planpilot.cli as cli

    config = cli.load_config(args.config)
    if not args.verbose:
        from planpilot.progress import RichSyncProgress

        with RichSyncProgress() as progress:
            pp = await cli.PlanPilot.from_config(config, progress=progress)
            candidate_plan_ids = await pp.discover_remote_plan_ids()
        selected_plan_id = cli._resolve_selected_plan_id(
            explicit_plan_id=args.plan_id,
            candidate_plan_ids=candidate_plan_ids,
        )
        with RichSyncProgress() as progress:
            pp = await cli.PlanPilot.from_config(config, progress=progress)
            result = await pp.map_sync(plan_id=selected_plan_id, dry_run=args.dry_run)
    else:
        pp = await cli.PlanPilot.from_config(config)
        candidate_plan_ids = await pp.discover_remote_plan_ids()
        selected_plan_id = cli._resolve_selected_plan_id(
            explicit_plan_id=args.plan_id,
            candidate_plan_ids=candidate_plan_ids,
        )
        result = await pp.map_sync(plan_id=selected_plan_id, dry_run=args.dry_run)

    if not args.dry_run:
        persist_sync_map(sync_map=result.sync_map, sync_path=config.sync_path, dry_run=False)
        persist_plan_from_remote(items=result.remote_plan_items, plan_paths=config.plan_paths)

    result = result.model_copy(update={"candidate_plan_ids": candidate_plan_ids})
    print(cli._format_map_sync_summary(result, config))
    return result


__all__ = ["format_map_sync_summary", "resolve_selected_plan_id", "run_map_sync"]
