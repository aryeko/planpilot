"""Command-line interface for PlanPilot."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from planpilot import (
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
    create_plan_stubs,
    detect_plan_paths,
    detect_target,
    load_config,
    scaffold_config,
    write_config,
)


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
    sync_parser.add_argument("--config", required=True, help="Path to planpilot.json")
    mode = sync_parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Preview mode")
    mode.add_argument("--apply", action="store_true", help="Apply mode")
    sync_parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")

    init_parser = subparsers.add_parser("init", help="Generate a planpilot.json config file")
    init_parser.add_argument(
        "--output", "-o", default="planpilot.json", help="Output file path (default: planpilot.json)"
    )
    init_parser.add_argument("--defaults", action="store_true", help="Use defaults without prompting")

    return parser


async def _run_sync(args: argparse.Namespace) -> SyncResult:
    config = load_config(args.config)

    if not args.verbose:
        from planpilot.progress import RichSyncProgress

        with RichSyncProgress() as progress:
            pp = await PlanPilot.from_config(config, progress=progress)
            result = await pp.sync(dry_run=args.dry_run)
    else:
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


def _run_init(args: argparse.Namespace) -> int:
    """Run the init wizard or defaults mode."""
    output = Path(args.output)

    if output.exists():
        if args.defaults:
            print(f"error: {output} already exists (use a different --output path)", file=sys.stderr)
            return 2
        try:
            import questionary

            if not questionary.confirm(f"{output} already exists. Overwrite?", default=False).ask():
                print("Aborted.")
                return 2
        except KeyboardInterrupt:
            print("\nAborted.")
            return 2

    if args.defaults:
        return _run_init_defaults(output)
    return _run_init_interactive(output)


def _run_init_defaults(output: Path) -> int:
    """Generate config with auto-detected defaults, no prompts."""
    target = detect_target() or "owner/repo"
    detected_paths = detect_plan_paths()
    plan_paths = (
        {k: str(v) for k, v in detected_paths.model_dump(exclude_none=True).items()} if detected_paths else None
    )

    try:
        config = scaffold_config(
            target=target,
            board_url="https://github.com/orgs/OWNER/projects/N",
            plan_paths=plan_paths,
        )
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    write_config(config, output)
    print(f"Config written to {output}")
    print("\nEdit the file to set your target and board_url, then run:")
    print(f"  planpilot sync --config {output} --dry-run")
    return 0


def _run_init_interactive(output: Path) -> int:
    """Run the interactive wizard using questionary."""
    try:
        import questionary
    except ImportError:  # pragma: no cover
        print("error: questionary is required for interactive init (pip install questionary)", file=sys.stderr)
        return 1

    try:
        # --- 1. Provider ---
        provider = questionary.select("Provider:", choices=["github"], default="github").ask()
        if provider is None:
            raise KeyboardInterrupt

        # --- 2. Target ---
        detected_target = detect_target()
        target = questionary.text(
            "Target repository (owner/repo):",
            default=detected_target or "",
            validate=lambda v: len(v.strip()) > 0 or "Target is required",
        ).ask()
        if target is None:
            raise KeyboardInterrupt
        target = target.strip()

        # --- 3. Board URL ---
        org = target.split("/")[0] if "/" in target else "OWNER"
        board_url = questionary.text(
            "Board URL (GitHub project URL):",
            default=f"https://github.com/orgs/{org}/projects/",
            validate=lambda v: len(v.strip()) > 0 or "Board URL is required",
        ).ask()
        if board_url is None:
            raise KeyboardInterrupt
        board_url = board_url.strip()

        # --- 4. Plan layout ---
        layout = questionary.select(
            "Plan file layout:",
            choices=[
                questionary.Choice("Split files (epics.json, stories.json, tasks.json)", value="split"),
                questionary.Choice("Unified file (plan.json)", value="unified"),
            ],
            default="split",
        ).ask()
        if layout is None:
            raise KeyboardInterrupt

        # --- 5. Plan paths ---
        detected_paths = detect_plan_paths()
        if layout == "split":
            defaults = {
                "epics": str(detected_paths.epics) if detected_paths and detected_paths.epics else ".plans/epics.json",
                "stories": (
                    str(detected_paths.stories) if detected_paths and detected_paths.stories else ".plans/stories.json"
                ),
                "tasks": str(detected_paths.tasks) if detected_paths and detected_paths.tasks else ".plans/tasks.json",
            }
            epics_path = questionary.text("Epics file path:", default=defaults["epics"]).ask()
            stories_path = questionary.text("Stories file path:", default=defaults["stories"]).ask()
            tasks_path = questionary.text("Tasks file path:", default=defaults["tasks"]).ask()
            if any(v is None for v in (epics_path, stories_path, tasks_path)):
                raise KeyboardInterrupt
            plan_paths: dict[str, str] = {"epics": epics_path, "stories": stories_path, "tasks": tasks_path}
        else:
            default_unified = (
                str(detected_paths.unified) if detected_paths and detected_paths.unified else ".plans/plan.json"
            )
            unified_path = questionary.text("Unified plan file path:", default=default_unified).ask()
            if unified_path is None:
                raise KeyboardInterrupt
            plan_paths = {"unified": unified_path}

        # --- 6. Sync map path ---
        sync_path = questionary.text("Sync map path:", default=".plans/sync-map.json").ask()
        if sync_path is None:
            raise KeyboardInterrupt

        # --- 7. Auth strategy ---
        auth = questionary.select(
            "Authentication strategy:",
            choices=[
                questionary.Choice("gh CLI (default)", value="gh-cli"),
                questionary.Choice("Environment variable (GITHUB_TOKEN)", value="env"),
                questionary.Choice("Static token", value="token"),
            ],
            default="gh-cli",
        ).ask()
        if auth is None:
            raise KeyboardInterrupt

        # --- 8. Advanced options ---
        adv_validation_mode = "strict"
        adv_max_concurrent = 1
        show_advanced = questionary.confirm("Configure advanced options?", default=False).ask()
        if show_advanced is None:
            raise KeyboardInterrupt
        if show_advanced:
            vm = questionary.select("Validation mode:", choices=["strict", "partial"], default="strict").ask()
            if vm is None:
                raise KeyboardInterrupt
            adv_validation_mode = vm
            mc = questionary.text(
                "Max concurrent operations (1-10):", default="1", validate=lambda v: v.isdigit() and 1 <= int(v) <= 10
            ).ask()
            if mc is None:
                raise KeyboardInterrupt
            adv_max_concurrent = int(mc)

        # --- Build and write config ---
        config = scaffold_config(
            provider=provider,
            target=target,
            board_url=board_url,
            auth=auth,
            plan_paths=plan_paths,
            sync_path=sync_path,
            validation_mode=adv_validation_mode,
            max_concurrent=adv_max_concurrent,
        )
        write_config(config, output)

        # --- 9. Create stub plan files ---
        stubs_needed = any(not Path(p).exists() for p in plan_paths.values())
        if stubs_needed and questionary.confirm("Create empty plan files?", default=True).ask():
            created = create_plan_stubs(plan_paths)
            for p in created:
                print(f"  Created {p}")

        # --- Summary ---
        print(f"\nConfig written to {output}")
        print("\nNext steps:")
        print("  1. Add your plan items to the plan files")
        print(f"  2. Preview:  planpilot sync --config {output} --dry-run")
        print(f"  3. Apply:    planpilot sync --config {output} --apply")
        return 0

    except KeyboardInterrupt:
        print("\nAborted.")
        return 2
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        return _run_init(args)

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
