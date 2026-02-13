"""CLI parser construction."""

from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, version


def _package_version() -> str:
    try:
        return version("planpilot")
    except PackageNotFoundError:
        return "0.0.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="planpilot")
    parser.add_argument("--version", action="version", version=f"%(prog)s {_package_version()}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync", help="Sync plan to provider")
    sync_parser.add_argument("--config", default="./planpilot.json", help="Path to planpilot.json")
    mode = sync_parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Preview mode")
    mode.add_argument("--apply", action="store_true", help="Apply mode")
    sync_parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")

    init_parser = subparsers.add_parser("init", help="Generate a planpilot.json config file")
    init_parser.add_argument(
        "--output",
        "-o",
        default="planpilot.json",
        help="Output file path (default: planpilot.json)",
    )
    init_parser.add_argument("--defaults", action="store_true", help="Use defaults without prompting")

    clean_parser = subparsers.add_parser("clean", help="Delete all issues belonging to a plan")
    clean_parser.add_argument("--config", default="./planpilot.json", help="Path to planpilot.json")
    clean_mode = clean_parser.add_mutually_exclusive_group(required=True)
    clean_mode.add_argument("--dry-run", action="store_true", help="Preview mode")
    clean_mode.add_argument("--apply", action="store_true", help="Apply mode")
    clean_parser.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Delete all planpilot-managed issues (by label), not just the current plan version",
    )
    clean_parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")

    map_parser = subparsers.add_parser("map", help="Sync-map operations")
    map_subparsers = map_parser.add_subparsers(dest="map_command", required=True)

    map_sync_parser = map_subparsers.add_parser("sync", help="Reconcile local sync map from remote metadata")
    map_sync_parser.add_argument("--config", default="./planpilot.json", help="Path to planpilot.json")
    map_sync_parser.add_argument(
        "--plan-id",
        default=None,
        help="Remote plan ID to reconcile (required for non-interactive mode if multiple IDs found)",
    )
    map_mode = map_sync_parser.add_mutually_exclusive_group(required=True)
    map_mode.add_argument("--dry-run", action="store_true", help="Preview mode")
    map_mode.add_argument("--apply", action="store_true", help="Apply mode")
    map_sync_parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")

    return parser


__all__ = ["build_parser"]
