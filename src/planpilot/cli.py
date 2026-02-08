"""Command-line interface for planpilot."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from planpilot.config import SyncConfig
from planpilot.exceptions import PlanPilotError
from planpilot.models.project import FieldConfig
from planpilot.providers.github.client import GhClient
from planpilot.providers.github.provider import GitHubProvider
from planpilot.rendering.markdown import MarkdownRenderer
from planpilot.sync.engine import SyncEngine


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the planpilot CLI.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(description="Sync plan epics/stories/tasks to GitHub issues and project.")
    parser.add_argument("--repo", required=True, help="GitHub repo (OWNER/REPO)")
    parser.add_argument("--project-url", required=True, help="GitHub Project URL")
    parser.add_argument("--epics-path", required=True, help="Path to epics.json")
    parser.add_argument("--stories-path", required=True, help="Path to stories.json")
    parser.add_argument("--tasks-path", required=True, help="Path to tasks.json")
    parser.add_argument("--sync-path", required=True, help="Path to write sync map")
    parser.add_argument("--label", default="codex", help="Label to apply")
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
    return parser


def _build_config(args: argparse.Namespace) -> SyncConfig:
    """Build a SyncConfig from parsed CLI arguments.

    Args:
        args: Parsed argparse namespace.

    Returns:
        Configured SyncConfig.
    """
    return SyncConfig(
        repo=args.repo,
        project_url=args.project_url,
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


async def _run_sync(config: SyncConfig) -> None:
    """Execute the sync pipeline.

    Args:
        config: Sync configuration.
    """
    provider = GitHubProvider(GhClient())
    renderer = MarkdownRenderer()
    engine = SyncEngine(provider=provider, renderer=renderer, config=config)
    result = await engine.sync()

    print(
        f"\nSync complete: {result.epics_created} epic(s), "
        f"{result.stories_created} story(s), {result.tasks_created} task(s)"
    )
    if result.dry_run:
        print("[dry-run] No changes were made to GitHub")


def main() -> int:
    """Entry point for the ``planpilot`` CLI command.

    Returns:
        Exit code: 0 on success, 2 on error.
    """
    parser = build_parser()
    args = parser.parse_args()

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
