import argparse
import sys
from .types import SyncConfig
from .sync import run_sync


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Sync plan epics/stories to GitHub issues and project.')
    parser.add_argument('--repo', required=True, help='GitHub repo (OWNER/REPO)')
    parser.add_argument('--project-url', required=True, help='GitHub Project URL')
    parser.add_argument('--epics-path', required=True, help='Path to epics.json')
    parser.add_argument('--stories-path', required=True, help='Path to stories.json')
    parser.add_argument('--tasks-path', required=True, help='Path to tasks.json')
    parser.add_argument('--sync-path', required=True, help='Path to write sync map')
    parser.add_argument('--label', default='codex', help='Label to apply')
    parser.add_argument('--status', default='Backlog', help='Project status option name')
    parser.add_argument('--priority', default='P1', help='Project priority option name')
    parser.add_argument('--iteration', default='active', help='Iteration title or "active" or "none"')
    parser.add_argument('--size-field', default='Size', help='Project size field name (empty to skip)')
    parser.add_argument('--size-from-tshirt', default='true', choices=['true', 'false'], help='Use estimate.tshirt for size')
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('--dry-run', action='store_true', help='Preview changes without creating/updating issues')
    mode_group.add_argument('--apply', action='store_true', help='Apply changes to GitHub (mutating mode)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = SyncConfig(
        repo=args.repo,
        project_url=args.project_url,
        epics_path=args.epics_path,
        stories_path=args.stories_path,
        tasks_path=args.tasks_path,
        sync_path=args.sync_path,
        label=args.label,
        status=args.status,
        priority=args.priority,
        iteration=args.iteration,
        size_field=args.size_field,
        size_from_tshirt=args.size_from_tshirt == 'true',
        apply=args.apply,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )
    try:
        run_sync(config)
        return 0
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
