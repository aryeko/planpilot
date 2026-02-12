"""Command-line interface for PlanPilot."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import httpx

from planpilot import (
    AuthenticationError,
    CleanResult,
    ConfigError,
    MapSyncResult,
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
from planpilot.contracts.exceptions import ProjectURLError
from planpilot.engine.progress import SyncProgress
from planpilot.providers.github.mapper import parse_project_url

_REQUIRED_CLASSIC_SCOPES = {"repo", "project"}


def _owner_from_target(target: str) -> str:
    return target.split("/", 1)[0].strip()


def _validate_target(value: str) -> bool | str:
    candidate = value.strip()
    parts = candidate.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return "Use target format owner/repo"
    return True


def _resolve_init_token(*, auth: str, target: str, static_token: str | None) -> str:
    from planpilot.auth.base import TokenResolver
    from planpilot.auth.resolvers.env import EnvTokenResolver
    from planpilot.auth.resolvers.gh_cli import GhCliTokenResolver
    from planpilot.auth.resolvers.static import StaticTokenResolver

    resolver: TokenResolver
    if auth == "gh-cli":
        hostname = "github.com"
        resolver = GhCliTokenResolver(hostname=hostname)
    elif auth == "env":
        resolver = EnvTokenResolver()
    elif auth == "token":
        resolver = StaticTokenResolver(token=static_token or "")
    else:  # defensive, should be unreachable due to prompt choices
        raise AuthenticationError(f"Unsupported auth mode: {auth}")
    return asyncio.run(resolver.resolve())


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "planpilot-init",
    }


def _check_classic_scopes(*, scopes_header: str | None) -> None:
    if scopes_header is None:
        return
    scopes = {s.strip() for s in scopes_header.split(",") if s.strip()}
    missing = _REQUIRED_CLASSIC_SCOPES - scopes
    if missing:
        needed = ", ".join(sorted(missing))
        raise AuthenticationError(f"Token is missing required GitHub scopes: {needed}")


def _validate_github_auth_for_init(*, token: str, target: str, progress: SyncProgress | None = None) -> str | None:
    owner, repo = target.split("/", 1)
    with httpx.Client(timeout=10.0) as client:
        if progress is not None:
            progress.phase_start("Init Auth")
        user_resp = client.get("https://api.github.com/user", headers=_github_headers(token))
        if user_resp.status_code != 200:
            error = AuthenticationError("GitHub authentication failed; verify your token/gh login and network access")
            if progress is not None:
                progress.phase_error("Init Auth", error)
            raise error
        try:
            _check_classic_scopes(scopes_header=user_resp.headers.get("x-oauth-scopes"))
        except AuthenticationError as error:
            if progress is not None:
                progress.phase_error("Init Auth", error)
            raise
        if progress is not None:
            progress.phase_done("Init Auth")

        if progress is not None:
            progress.phase_start("Init Repo")
        repo_resp = client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=_github_headers(token))
        if repo_resp.status_code != 200:
            error = AuthenticationError(
                f"Cannot access target repository '{target}'; verify repo scope/permissions and repo visibility"
            )
            if progress is not None:
                progress.phase_error("Init Repo", error)
            raise error
        if progress is not None:
            progress.phase_done("Init Repo")

        if progress is not None:
            progress.phase_start("Init Projects")
        viewer_projects_query = {"query": "query { viewer { projectsV2(first: 1) { nodes { id } } } }"}
        projects_resp = client.post(
            "https://api.github.com/graphql",
            headers=_github_headers(token),
            json=viewer_projects_query,
        )
        payload = (
            projects_resp.json() if projects_resp.headers.get("content-type", "").startswith("application/json") else {}
        )
        if projects_resp.status_code != 200 or payload.get("errors"):
            error = AuthenticationError(
                "Token does not have sufficient project permissions; ensure project access is granted"
            )
            if progress is not None:
                progress.phase_error("Init Projects", error)
            raise error
        if progress is not None:
            progress.phase_done("Init Projects")

        if progress is not None:
            progress.phase_start("Init Owner")
        owner_resp = client.get(f"https://api.github.com/users/{owner}", headers=_github_headers(token))
        if owner_resp.status_code != 200:
            if progress is not None:
                progress.phase_done("Init Owner")
            return None
        owner_payload = owner_resp.json()
        owner_type = owner_payload.get("type")
        if owner_type == "Organization":
            if progress is not None:
                progress.phase_done("Init Owner")
            return "org"
        if owner_type == "User":
            if progress is not None:
                progress.phase_done("Init Owner")
            return "user"
        if progress is not None:
            progress.phase_done("Init Owner")
        return None


def _default_board_url_for_target(target: str) -> str:
    owner = target.split("/")[0] if "/" in target else "OWNER"
    return f"https://github.com/orgs/{owner}/projects/1"


def _default_board_url_with_owner_type(target: str, owner_type: str | None) -> str:
    owner = _owner_from_target(target) if "/" in target else "OWNER"
    segment = "users" if owner_type == "user" else "orgs"
    return f"https://github.com/{segment}/{owner}/projects/1"


def _validate_board_url(value: str) -> bool | str:
    candidate = value.strip()
    if not candidate:
        return "Board URL is required"
    try:
        parse_project_url(candidate)
    except ProjectURLError:
        return "Use a full GitHub Projects URL (orgs|users)/<owner>/projects/<number>"
    return True


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
        "--output", "-o", default="planpilot.json", help="Output file path (default: planpilot.json)"
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


async def _run_map_sync(args: argparse.Namespace) -> MapSyncResult:
    config = load_config(args.config)
    if not args.verbose:
        from planpilot.progress import RichSyncProgress

        with RichSyncProgress() as progress:
            pp = await PlanPilot.from_config(config, progress=progress)
            candidate_plan_ids = await pp.discover_remote_plan_ids()
        selected_plan_id = _resolve_selected_plan_id(
            explicit_plan_id=args.plan_id,
            candidate_plan_ids=candidate_plan_ids,
        )
        with RichSyncProgress() as progress:
            pp = await PlanPilot.from_config(config, progress=progress)
            result = await pp.map_sync(plan_id=selected_plan_id, dry_run=args.dry_run)
    else:
        pp = await PlanPilot.from_config(config)
        candidate_plan_ids = await pp.discover_remote_plan_ids()
        selected_plan_id = _resolve_selected_plan_id(
            explicit_plan_id=args.plan_id,
            candidate_plan_ids=candidate_plan_ids,
        )
        result = await pp.map_sync(plan_id=selected_plan_id, dry_run=args.dry_run)
    result = result.model_copy(update={"candidate_plan_ids": candidate_plan_ids})
    print(_format_map_sync_summary(result, config))
    return result


def _resolve_selected_plan_id(*, explicit_plan_id: str | None, candidate_plan_ids: list[str]) -> str:
    if explicit_plan_id is not None and explicit_plan_id.strip():
        return explicit_plan_id.strip()

    if not candidate_plan_ids:
        raise ConfigError(
            "No remote PLAN_ID values were discovered; run sync first or pass --plan-id to target a known plan ID"
        )
    if len(candidate_plan_ids) == 1:
        return candidate_plan_ids[0]
    if not sys.stdin.isatty():
        raise ConfigError("Multiple remote PLAN_ID values found; rerun with --plan-id in non-interactive mode")

    try:
        import questionary
    except ImportError as exc:  # pragma: no cover
        raise ConfigError(
            "questionary is required for interactive plan-id selection (install questionary or pass --plan-id)"
        ) from exc

    selected = questionary.select("Select remote PLAN_ID to reconcile:", choices=candidate_plan_ids).ask()
    if selected is None:
        raise ConfigError("Aborted plan-id selection")
    return str(selected)


def _format_summary(result: SyncResult, config: PlanPilotConfig) -> str:
    mode = "dry-run" if result.dry_run else "apply"
    created_epics = result.items_created.get(PlanItemType.EPIC, 0)
    created_stories = result.items_created.get(PlanItemType.STORY, 0)
    created_tasks = result.items_created.get(PlanItemType.TASK, 0)
    total_created = created_epics + created_stories + created_tasks

    total_by_type = {PlanItemType.EPIC: 0, PlanItemType.STORY: 0, PlanItemType.TASK: 0}
    for entry in result.sync_map.entries.values():
        if entry.item_type in total_by_type:
            total_by_type[entry.item_type] += 1

    total_items = len(result.sync_map.entries)
    total_matched = total_items - total_created

    matched_epics = total_by_type[PlanItemType.EPIC] - created_epics
    matched_stories = total_by_type[PlanItemType.STORY] - created_stories
    matched_tasks = total_by_type[PlanItemType.TASK] - created_tasks

    def _type_breakdown(epics: int, stories: int, tasks: int) -> str:
        parts: list[str] = []
        if epics:
            parts.append(f"{epics} epic{'s' if epics != 1 else ''}")
        if stories:
            parts.append(f"{stories} stor{'ies' if stories != 1 else 'y'}")
        if tasks:
            parts.append(f"{tasks} task{'s' if tasks != 1 else ''}")
        return ", ".join(parts) if parts else "none"

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
            _type_breakdown(
                total_by_type[PlanItemType.EPIC],
                total_by_type[PlanItemType.STORY],
                total_by_type[PlanItemType.TASK],
            ),
        ),
    ]

    if total_created > 0:
        lines.append(f"  Created:   {total_created} ({_type_breakdown(created_epics, created_stories, created_tasks)})")
    if total_matched > 0:
        lines.append(f"  Matched:   {total_matched} ({_type_breakdown(matched_epics, matched_stories, matched_tasks)})")
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


async def _run_clean(args: argparse.Namespace) -> CleanResult:
    config = load_config(args.config)
    all_plans: bool = getattr(args, "all", False)

    if not args.verbose:
        from planpilot.progress import RichSyncProgress

        with RichSyncProgress() as progress:
            pp = await PlanPilot.from_config(config, progress=progress)
            result = await pp.clean(dry_run=args.dry_run, all_plans=all_plans)
    else:
        pp = await PlanPilot.from_config(config)
        result = await pp.clean(dry_run=args.dry_run, all_plans=all_plans)

    print(_format_clean_summary(result))
    return result


def _format_clean_summary(result: CleanResult) -> str:
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


def _format_map_sync_summary(result: MapSyncResult, config: PlanPilotConfig) -> str:
    mode = "dry-run" if result.dry_run else "apply"

    def _fmt_ids(values: list[str]) -> str:
        if not values:
            return "none"
        return ", ".join(values)

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
        f"  Added:        {len(result.added)} ({_fmt_ids(result.added)})",
        f"  Updated:      {len(result.updated)} ({_fmt_ids(result.updated)})",
        f"  Removed:      {len(result.removed)} ({_fmt_ids(result.removed)})",
        "",
        f"  Sync map:     {config.sync_path}",
    ]
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
    board_url = _default_board_url_for_target(target)

    try:
        config = scaffold_config(
            target=target,
            board_url=board_url,
            plan_paths=plan_paths,
            include_defaults=True,
        )
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    write_config(config, output)
    print(f"Config written to {output}")
    print("\nEdit board_url if your project is under /users/ instead of /orgs/, then run:")
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

        # --- 2. Auth strategy ---
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
        auth_token: str | None = None
        if auth == "token":
            auth_token = questionary.password(
                "GitHub token (PAT):",
                validate=lambda v: len(v.strip()) > 0 or "Token is required for static token auth",
            ).ask()
            if auth_token is None:
                raise KeyboardInterrupt
            auth_token = auth_token.strip()

        # --- 3. Target ---
        detected_target = detect_target()
        target = questionary.text(
            "Target repository (owner/repo):",
            default=detected_target or "",
            validate=_validate_target,
        ).ask()
        if target is None:
            raise KeyboardInterrupt
        target = target.strip()

        owner_type: str | None = None
        if provider == "github":
            if sys.stderr.isatty():
                from planpilot.progress import RichSyncProgress

                with RichSyncProgress() as progress:
                    resolved_token = _resolve_init_token(auth=auth, target=target, static_token=auth_token)
                    owner_type = _validate_github_auth_for_init(token=resolved_token, target=target, progress=progress)
            else:
                resolved_token = _resolve_init_token(auth=auth, target=target, static_token=auth_token)
                owner_type = _validate_github_auth_for_init(token=resolved_token, target=target)

        # --- 4. Board URL ---
        default_board_url = _default_board_url_with_owner_type(target, owner_type)
        board_url = questionary.text(
            "Board URL (GitHub project URL):",
            default=default_board_url,
            validate=_validate_board_url,
        ).ask()
        if board_url is None:
            raise KeyboardInterrupt
        board_url = board_url.strip()

        # --- 5. Plan layout ---
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

        # --- 6. Plan paths ---
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

        # --- 7. Sync map path ---
        sync_path = questionary.text("Sync map path:", default=".plans/sync-map.json").ask()
        if sync_path is None:
            raise KeyboardInterrupt

        # --- 8. Advanced options ---
        adv_validation_mode = "strict"
        adv_max_concurrent = 1
        adv_label = "planpilot"
        adv_field_config: dict[str, object] | None = None
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
            label = questionary.text("Discovery label:", default="planpilot").ask()
            if label is None:
                raise KeyboardInterrupt
            adv_label = label.strip() or "planpilot"
            configure_fields = questionary.confirm("Configure field defaults?", default=False).ask()
            if configure_fields is None:
                raise KeyboardInterrupt
            if configure_fields:
                status = questionary.text("Default status:", default="Backlog").ask()
                priority = questionary.text("Default priority:", default="P1").ask()
                iteration = questionary.text("Default iteration:", default="active").ask()
                size_field = questionary.text("Size field name:", default="Size").ask()
                size_from_tshirt = questionary.confirm("Map t-shirt estimate to size field?", default=True).ask()
                if None in {status, priority, iteration, size_field, size_from_tshirt}:
                    raise KeyboardInterrupt
                strategy_default = "label" if owner_type == "user" else "issue-type"
                strategy = questionary.select(
                    "Create type strategy:",
                    choices=["issue-type", "label"],
                    default=strategy_default,
                ).ask()
                if strategy is None:
                    raise KeyboardInterrupt
                adv_field_config = {
                    "status": status.strip() or "Backlog",
                    "priority": priority.strip() or "P1",
                    "iteration": iteration.strip() or "active",
                    "size_field": size_field.strip() or "Size",
                    "size_from_tshirt": bool(size_from_tshirt),
                    "create_type_strategy": strategy,
                }

        # --- Build and write config ---
        if auth == "token":
            print(
                "warning: static token auth stores token in plaintext in planpilot.json; "
                "prefer gh-cli or env auth when possible",
                file=sys.stderr,
            )

        config = scaffold_config(
            provider=provider,
            target=target,
            board_url=board_url,
            auth=auth,
            token=auth_token,
            plan_paths=plan_paths,
            sync_path=sync_path,
            validation_mode=adv_validation_mode,
            label=adv_label,
            max_concurrent=adv_max_concurrent,
            field_config=adv_field_config,
            include_defaults=True,
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
    except AuthenticationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        return _run_init(args)
    if args.command == "map":
        if args.map_command != "sync":
            print(f"error: unsupported map command: {args.map_command}", file=sys.stderr)
            return 2
        if args.verbose:
            logging.basicConfig(level=logging.DEBUG, format="%(name)s %(message)s", stream=sys.stderr)
        try:
            asyncio.run(_run_map_sync(args))
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

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(message)s", stream=sys.stderr)

    try:
        if args.command == "sync":
            asyncio.run(_run_sync(args))
        elif args.command == "clean":
            asyncio.run(_run_clean(args))
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
