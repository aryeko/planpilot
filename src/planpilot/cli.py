"""Command-line interface for planpilot."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from planpilot import __version__
from planpilot.config import SyncConfig
from planpilot.exceptions import PlanPilotError
from planpilot.models.project import FieldConfig
from planpilot.models.sync import SyncResult
from planpilot.providers.factory import create_provider
from planpilot.rendering.markdown import MarkdownRenderer
from planpilot.sync.engine import SyncEngine

# Import GitHub provider to trigger registration
import planpilot.providers.github  # noqa: F401


def _add_sync_args(parser: argparse.ArgumentParser) -> None:
    """Attach shared sync arguments to a parser."""
    parser.add_argument("--provider", default="github", help="Provider name (default: github)")
    parser.add_argument("--target", required=True, help="Target designation (e.g. OWNER/REPO for GitHub)")
    parser.add_argument("--board-url", required=False, help="Board URL (optional)")
    parser.add_argument("--epics-path", required=True, help="Path to epics.json")
    parser.add_argument("--stories-path", required=True, help="Path to stories.json")
    parser.add_argument("--tasks-path", required=True, help="Path to tasks.json")
    parser.add_argument("--sync-path", required=True, help="Path to write sync map")
    parser.add_argument("--label", default="planpilot", help="Label to apply")
    parser.add_argument("--status", default="Backlog", help="Project status option name")
    parser.add_argument("--priority", default="P1", help="Project priority option name")
    parser.add_argument(
        "--iteration",
        default="active",
        help='Iteration title or "active" or "none"',
    )
    parser.add_argument("--size-field", default="Size", help="Project size field name")
    parser.add_argument(
        "--no-size-from-tshirt",
        dest="size_from_tshirt",
        action="store_false",
        default=True,
        help="Disable t-shirt size mapping",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without creating/updating issues",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to GitHub (mutating mode)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the planpilot CLI.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(description="Sync plan epics/stories/tasks to GitHub issues and project.")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    _add_sync_args(parser)
    return parser


def _build_config(args: argparse.Namespace) -> SyncConfig:
    """Build a SyncConfig from parsed CLI arguments.

    Args:
        args: Parsed argparse namespace.

    Returns:
        Configured SyncConfig.
    """
    return SyncConfig(
        provider=args.provider,
        target=args.target,
        board_url=args.board_url,
        epics_path=args.epics_path,
        stories_path=args.stories_path,
        tasks_path=args.tasks_path,
        sync_path=args.sync_path,
        label=args.label,
        field_config=FieldConfig(
            status=args.status,
            priority=args.priority,
            iteration=args.iteration,
            size_field=args.size_field,
            size_from_tshirt=args.size_from_tshirt,
        ),
        dry_run=args.dry_run,
        verbose=args.verbose,
    )


def _format_summary(result: SyncResult, config: SyncConfig) -> str:
    """Format a human-readable execution summary.

    Args:
        result: The sync result.
        config: The sync configuration.

    Returns:
        Multi-line summary string.
    """
    sm = result.sync_map
    mode = "dry-run" if result.dry_run else "apply"
    lines = [
        "",
        f"planpilot - sync complete ({mode})",
        "",
        f"  Plan ID:   {sm.plan_id}",
        f"  Target:    {sm.target}",
        f"  Board:     {sm.board_url or '(none)'}",
        "",
    ]

    total_existing = (
        (len(sm.epics) - result.epics_created)
        + (len(sm.stories) - result.stories_created)
        + (len(sm.tasks) - result.tasks_created)
    )
    lines.append(
        f"  Created:   {result.epics_created} epic(s), "
        f"{result.stories_created} story(s), {result.tasks_created} task(s)"
    )
    if total_existing > 0:
        lines.append(
            f"  Existing:  {len(sm.epics) - result.epics_created} epic(s), "
            f"{len(sm.stories) - result.stories_created} story(s), "
            f"{len(sm.tasks) - result.tasks_created} task(s)"
        )
    lines.append("")

    # Item table
    for eid, entry in sm.epics.items():
        lines.append(f"  Epic   {eid:<6}  {entry.key:<5}  {entry.url}")
    for sid, entry in sm.stories.items():
        lines.append(f"  Story  {sid:<6}  {entry.key:<5}  {entry.url}")
    for tid, entry in sm.tasks.items():
        lines.append(f"  Task   {tid:<6}  {entry.key:<5}  {entry.url}")

    lines.append("")
    lines.append(f"  Sync map:  {config.sync_path}")

    if result.dry_run:
        lines.append("")
        lines.append("  [dry-run] No changes were made")

    lines.append("")
    return "\n".join(lines)


async def _run_sync(config: SyncConfig) -> None:
    """Execute the sync pipeline.

    Args:
        config: Sync configuration.
    """
    # Provider lifecycle is managed here in the CLI layer
    provider = create_provider(
        config.provider,
        target=config.target,
        board_url=config.board_url,
        label=config.label,
        field_config=config.field_config,
    )
    
    async with provider:
        renderer = MarkdownRenderer()
        engine = SyncEngine(provider=provider, renderer=renderer, config=config)
        result = await engine.sync()
        print(_format_summary(result, config))


def main() -> int:
    """Entry point for the ``planpilot`` CLI command.

    Returns:
        Exit code: 0 on success, 2 on error.
    """
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:])

    if args.verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(name)s %(message)s",
            stream=sys.stderr,
        )

    config = _build_config(args)

    try:
        asyncio.run(_run_sync(config))
        return 0
    except PlanPilotError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
