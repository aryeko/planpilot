"""Clean command formatting."""

from __future__ import annotations

import argparse

from planpilot import CleanResult


def format_clean_summary(result: CleanResult) -> str:
    mode = "dry-run" if result.dry_run else "apply"

    lines = [
        "",
        f"planpilot - clean complete ({mode})",
        "",
        f"  Plan ID:    {result.plan_id}",
        f"  Deleted:    {result.items_deleted} issue{'s' if result.items_deleted != 1 else ''}",
        "",
    ]

    if result.dry_run:
        lines.append("  [dry-run] No issues were deleted")
        lines.append("")

    return "\n".join(lines)


async def run_clean(args: argparse.Namespace) -> CleanResult:
    import planpilot.cli as cli

    config = cli.load_config(args.config)
    all_plans: bool = getattr(args, "all", False)

    if not args.verbose:
        from planpilot.progress import RichSyncProgress

        with RichSyncProgress() as progress:
            pp = await cli.PlanPilot.from_config(config, progress=progress)
            result = await pp.clean(dry_run=args.dry_run, all_plans=all_plans)
    else:
        pp = await cli.PlanPilot.from_config(config)
        result = await pp.clean(dry_run=args.dry_run, all_plans=all_plans)

    print(cli._format_clean_summary(result))
    return result


__all__ = ["format_clean_summary", "run_clean"]
