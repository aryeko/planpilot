"""Config loading and provider-specific validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from planpilot.core.contracts.config import PlanPaths, PlanPilotConfig
from planpilot.core.contracts.exceptions import ConfigError, ProjectURLError
from planpilot.core.targets.github_project import parse_project_url


def _resolve_path(value: Path | None, *, base_dir: Path) -> Path | None:
    if value is None:
        return None
    if value.is_absolute():
        return value
    return (base_dir / value).resolve()


def _validate_provider_specific_config(config: PlanPilotConfig) -> None:
    if config.provider != "github":
        return

    try:
        owner_type, _, _ = parse_project_url(config.board_url)
    except ProjectURLError as exc:
        raise ConfigError(str(exc)) from exc

    strategy = config.field_config.create_type_strategy
    if strategy not in {"issue-type", "label"}:
        raise ConfigError("field_config.create_type_strategy must be one of: issue-type, label")
    if owner_type == "user" and strategy != "label":
        raise ConfigError("GitHub user-owned projects require field_config.create_type_strategy='label'")


def load_config(path: str | Path) -> PlanPilotConfig:
    config_path = Path(path).expanduser().resolve()
    config_dir = config_path.parent

    try:
        raw_payload: Any = json.loads(config_path.read_text(encoding="utf-8"))
        parsed = PlanPilotConfig.model_validate(raw_payload)
    except OSError as exc:
        raise ConfigError(f"failed reading config file: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in config file: {config_path}") from exc
    except ValidationError as exc:
        raise ConfigError(f"invalid config: {exc}") from exc

    resolved_paths = PlanPaths(
        epics=_resolve_path(parsed.plan_paths.epics, base_dir=config_dir),
        stories=_resolve_path(parsed.plan_paths.stories, base_dir=config_dir),
        tasks=_resolve_path(parsed.plan_paths.tasks, base_dir=config_dir),
        unified=_resolve_path(parsed.plan_paths.unified, base_dir=config_dir),
    )
    resolved_config = parsed.model_copy(
        update={
            "plan_paths": resolved_paths,
            "sync_path": _resolve_path(parsed.sync_path, base_dir=config_dir),
        }
    )
    _validate_provider_specific_config(resolved_config)
    return resolved_config
