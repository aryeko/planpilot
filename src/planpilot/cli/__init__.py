"""Command-line interface for PlanPilot."""

from __future__ import annotations

import asyncio
import logging as logging
from typing import Protocol

from planpilot import AuthenticationError, resolve_init_token, validate_board_url, validate_github_auth_for_init
from planpilot import ConfigError as ConfigError
from planpilot import PlanPilot as PlanPilot
from planpilot import create_plan_stubs as create_plan_stubs
from planpilot import detect_plan_paths as detect_plan_paths
from planpilot import detect_target as detect_target
from planpilot import load_config as load_config
from planpilot import scaffold_config as scaffold_config
from planpilot import write_config as write_config
from planpilot.cli.app import main as main
from planpilot.cli.commands import clean as clean_command
from planpilot.cli.commands import init as init_command
from planpilot.cli.commands import map_sync as map_sync_command
from planpilot.cli.commands import sync as sync_command
from planpilot.cli.parser import _package_version as _parser_package_version
from planpilot.cli.parser import build_parser as build_parser

_REQUIRED_CLASSIC_SCOPES = {"repo", "project"}

_format_summary = sync_command.format_sync_summary
_format_clean_summary = clean_command.format_clean_summary
_format_map_sync_summary = map_sync_command.format_map_sync_summary


_run_init = init_command.run_init
_run_init_defaults = init_command.run_init_defaults
_run_init_interactive = init_command.run_init_interactive
_run_sync = sync_command.run_sync
_run_clean = clean_command.run_clean
_resolve_selected_plan_id = map_sync_command.resolve_selected_plan_id
_run_map_sync = map_sync_command.run_map_sync


class _InitProgress(Protocol):
    def phase_start(self, phase: str, total: int | None = None) -> None: ...

    def phase_done(self, phase: str) -> None: ...

    def phase_error(self, phase: str, error: BaseException) -> None: ...


def _owner_from_target(target: str) -> str:
    return target.split("/", 1)[0].strip()


def _validate_target(value: str) -> bool | str:
    candidate = value.strip()
    parts = candidate.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return "Use target format owner/repo"
    return True


def _resolve_init_token(*, auth: str, target: str, static_token: str | None) -> str:
    del target
    return resolve_init_token(auth=auth, static_token=static_token, run_async=asyncio.run)


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


def _validate_github_auth_for_init(*, token: str, target: str, progress: _InitProgress | None = None) -> str | None:
    return validate_github_auth_for_init(token=token, target=target, progress=progress)


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
    if not validate_board_url(candidate):
        return "Use a full GitHub Projects URL (orgs|users)/<owner>/projects/<number>"
    return True


_package_version = _parser_package_version
