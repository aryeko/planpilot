"""CLI app entrypoint and error mapping."""

from __future__ import annotations

import sys

from planpilot import AuthenticationError, ConfigError, PlanLoadError, PlanValidationError, ProviderError, SyncError


def main(argv: list[str] | None = None) -> int:
    import planpilot.cli as cli

    parser = cli.build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        return cli._run_init(args)
    if args.command == "map":
        if args.map_command != "sync":
            print(f"error: unsupported map command: {args.map_command}", file=sys.stderr)
            return 2
        if args.verbose:
            cli.logging.basicConfig(level=cli.logging.DEBUG, format="%(name)s %(message)s", stream=sys.stderr)
        try:
            cli.asyncio.run(cli._run_map_sync(args))
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
        cli.logging.basicConfig(level=cli.logging.DEBUG, format="%(name)s %(message)s", stream=sys.stderr)

    try:
        if args.command == "sync":
            cli.asyncio.run(cli._run_sync(args))
        elif args.command == "clean":
            cli.asyncio.run(cli._run_clean(args))
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


__all__ = ["main"]
