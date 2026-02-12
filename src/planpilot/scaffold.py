"""Config scaffolding and environment detection helpers."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from planpilot.contracts.config import PlanPaths, PlanPilotConfig
from planpilot.contracts.exceptions import ConfigError, ProjectURLError
from planpilot.providers.github.mapper import parse_project_url

# Defaults used by scaffold_config when no value is provided.
_SPLIT_DEFAULTS = {
    "epics": ".plans/epics.json",
    "stories": ".plans/stories.json",
    "tasks": ".plans/tasks.json",
}
_SYNC_PATH_DEFAULT = ".plans/sync-map.json"

# Patterns for parsing git remote URLs.
_SSH_RE = re.compile(r"^git@[^:]+:(?P<slug>[^/]+/[^/]+?)(?:\.git)?$")
_HTTPS_RE = re.compile(r"^https?://[^/]+/(?P<slug>[^/]+/[^/]+?)(?:\.git)?/?$")

# Directories to scan for plan files.
_PLAN_DIRS = [".plans", "plans"]
_SPLIT_FILES = {"epics.json", "stories.json", "tasks.json"}
_UNIFIED_FILES = {"plan.json"}


def detect_target() -> str | None:
    """Best-effort detection of ``owner/repo`` from the git remote.

    Parses the ``origin`` remote URL (SSH or HTTPS) and returns the slug.
    Returns ``None`` when not inside a git repository, when ``git`` is not
    installed, or when the remote URL cannot be parsed.
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        url = result.stdout.strip()
    except Exception:  # best-effort
        return None

    for pattern in (_SSH_RE, _HTTPS_RE):
        match = pattern.match(url)
        if match:
            return match.group("slug")
    return None


def detect_plan_paths(base: Path | None = None) -> PlanPaths | None:
    """Scan common directories for existing plan files.

    Checks ``.plans/`` and ``plans/`` under *base* (defaults to cwd) for
    split plan files (``epics.json``, ``stories.json``, ``tasks.json``) or a
    unified plan file (``plan.json``).  Returns a :class:`PlanPaths` when a
    coherent set is found, or ``None`` otherwise.
    """
    try:
        base = base or Path.cwd()
        for dirname in _PLAN_DIRS:
            plan_dir = base / dirname
            if not plan_dir.is_dir():
                continue

            existing = {f.name for f in plan_dir.iterdir() if f.is_file()}

            # Prefer split layout if all three files exist.
            if existing >= _SPLIT_FILES:
                return PlanPaths(
                    epics=Path(f"{dirname}/epics.json"),
                    stories=Path(f"{dirname}/stories.json"),
                    tasks=Path(f"{dirname}/tasks.json"),
                )

            # Fall back to unified if plan.json exists.
            if existing >= _UNIFIED_FILES:
                return PlanPaths(unified=Path(f"{dirname}/plan.json"))

    except Exception:  # best-effort
        pass
    return None


def scaffold_config(
    *,
    target: str,
    board_url: str,
    provider: str = "github",
    auth: str = "gh-cli",
    token: str | None = None,
    plan_paths: dict[str, str] | None = None,
    sync_path: str = _SYNC_PATH_DEFAULT,
    validation_mode: str = "strict",
    label: str = "planpilot",
    max_concurrent: int = 1,
    field_config: dict[str, Any] | None = None,
    include_defaults: bool = False,
) -> dict[str, Any]:
    """Build and validate a planpilot config dict.

    Accepts configuration values, validates them through
    :class:`PlanPilotConfig`, and returns a minimal JSON-serialisable ``dict``
    with default-valued fields omitted.

    Raises :class:`ConfigError` when validation fails.
    """
    if plan_paths is None:
        plan_paths = dict(_SPLIT_DEFAULTS)

    raw: dict[str, Any] = {
        "provider": provider,
        "target": target,
        "board_url": board_url,
        "plan_paths": plan_paths,
    }

    # Optionally include defaults for explicit, user-facing init output.
    if include_defaults or auth != "gh-cli":
        raw["auth"] = auth
    if token is not None:
        raw["token"] = token
    if include_defaults or sync_path != _SYNC_PATH_DEFAULT:
        raw["sync_path"] = sync_path
    if include_defaults or validation_mode != "strict":
        raw["validation_mode"] = validation_mode
    if include_defaults or label != "planpilot":
        raw["label"] = label
    if include_defaults or max_concurrent != 1:
        raw["max_concurrent"] = max_concurrent
    resolved_field_config = dict(field_config or {})
    if provider == "github":
        try:
            owner_type, _, _ = parse_project_url(board_url)
        except ProjectURLError as exc:
            raise ConfigError(str(exc)) from exc

        strategy = resolved_field_config.get("create_type_strategy")
        if owner_type == "user":
            if strategy is None:
                resolved_field_config["create_type_strategy"] = "label"
            elif strategy != "label":
                raise ConfigError("GitHub user-owned projects require field_config.create_type_strategy='label'")

    if resolved_field_config:
        raw["field_config"] = resolved_field_config

    # Validate through PlanPilotConfig to ensure consistency.
    try:
        PlanPilotConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"invalid config: {exc}") from exc

    return raw


def write_config(config: dict[str, Any], path: Path) -> None:
    """Write a config dict to a JSON file."""
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def create_plan_stubs(plan_paths: dict[str, str], *, base: Path | None = None) -> list[Path]:
    """Create empty plan files that don't already exist.

    Returns the list of paths that were created.
    """
    import json

    base = base or Path.cwd()
    created: list[Path] = []

    for key, rel_path in plan_paths.items():
        full = base / rel_path
        if full.exists():
            continue
        full.parent.mkdir(parents=True, exist_ok=True)
        if key == "unified":
            full.write_text(json.dumps({"items": []}, indent=2) + "\n", encoding="utf-8")
        else:
            full.write_text(json.dumps([], indent=2) + "\n", encoding="utf-8")
        created.append(full)

    return created
