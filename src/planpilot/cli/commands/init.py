"""Init command handlers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def run_init(args: argparse.Namespace) -> int:
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
        return run_init_defaults(output)
    return run_init_interactive(output)


def run_init_defaults(output: Path) -> int:
    """Generate config with auto-detected defaults, no prompts."""
    import planpilot.cli as cli

    target = cli.detect_target() or "owner/repo"
    detected_paths = cli.detect_plan_paths()
    plan_paths = (
        {k: str(v) for k, v in detected_paths.model_dump(exclude_none=True).items()} if detected_paths else None
    )
    board_url = cli._default_board_url_for_target(target)

    try:
        config = cli.scaffold_config(
            target=target,
            board_url=board_url,
            plan_paths=plan_paths,
            include_defaults=True,
        )
    except cli.ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    cli.write_config(config, output)
    print(f"Config written to {output}")
    print("\nEdit board_url if your project is under /users/ instead of /orgs/, then run:")
    print(f"  planpilot sync --config {output} --dry-run")
    return 0


def run_init_interactive(output: Path) -> int:
    """Run the interactive wizard using questionary."""
    import planpilot.cli as cli

    try:
        import questionary
    except ImportError:  # pragma: no cover
        print("error: questionary is required for interactive init (pip install questionary)", file=sys.stderr)
        return 1

    try:
        provider = questionary.select("Provider:", choices=["github"], default="github").ask()
        if provider is None:
            raise KeyboardInterrupt

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

        detected_target = cli.detect_target()
        target = questionary.text(
            "Target repository (owner/repo):",
            default=detected_target or "",
            validate=cli._validate_target,
        ).ask()
        if target is None:
            raise KeyboardInterrupt
        target = target.strip()

        owner_type: str | None = None
        if provider == "github":
            if sys.stderr.isatty():
                from planpilot.progress import RichSyncProgress

                with RichSyncProgress() as progress:
                    resolved_token = cli._resolve_init_token(auth=auth, target=target, static_token=auth_token)
                    owner_type = cli._validate_github_auth_for_init(
                        token=resolved_token,
                        target=target,
                        progress=progress,
                    )
            else:
                resolved_token = cli._resolve_init_token(auth=auth, target=target, static_token=auth_token)
                owner_type = cli._validate_github_auth_for_init(token=resolved_token, target=target)

        default_board_url = cli._default_board_url_with_owner_type(target, owner_type)
        board_url = questionary.text(
            "Board URL (GitHub project URL):",
            default=default_board_url,
            validate=cli._validate_board_url,
        ).ask()
        if board_url is None:
            raise KeyboardInterrupt
        board_url = board_url.strip()

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

        detected_paths = cli.detect_plan_paths()
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

        sync_path = questionary.text("Sync map path:", default=".plans/sync-map.json").ask()
        if sync_path is None:
            raise KeyboardInterrupt

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

        if auth == "token":
            print(
                "warning: static token auth stores token in plaintext in planpilot.json; "
                "prefer gh-cli or env auth when possible",
                file=sys.stderr,
            )

        config = cli.scaffold_config(
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
        cli.write_config(config, output)

        stubs_needed = any(not Path(p).exists() for p in plan_paths.values())
        if stubs_needed and questionary.confirm("Create empty plan files?", default=True).ask():
            created = cli.create_plan_stubs(plan_paths)
            for p in created:
                print(f"  Created {p}")

        print(f"\nConfig written to {output}")
        print("\nNext steps:")
        print("  1. Add your plan items to the plan files")
        print(f"  2. Preview:  planpilot sync --config {output} --dry-run")
        print(f"  3. Apply:    planpilot sync --config {output} --apply")
        return 0

    except KeyboardInterrupt:
        print("\nAborted.")
        return 2
    except cli.ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except cli.AuthenticationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4


__all__ = ["run_init", "run_init_defaults", "run_init_interactive"]
