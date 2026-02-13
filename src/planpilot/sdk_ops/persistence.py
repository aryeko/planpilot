"""Persistence helpers for SDK operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from planpilot.contracts.config import PlanPilotConfig
from planpilot.contracts.exceptions import ConfigError, SyncError
from planpilot.contracts.sync import SyncMap


def output_sync_path(*, config: PlanPilotConfig, dry_run: bool) -> Path:
    if not dry_run:
        return config.sync_path
    return Path(f"{config.sync_path}.dry-run")


def persist_sync_map(*, config: PlanPilotConfig, sync_map: SyncMap, dry_run: bool) -> None:
    path = output_sync_path(config=config, dry_run=dry_run)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(sync_map.model_dump_json(indent=2), encoding="utf-8")
    except OSError as exc:
        raise SyncError(f"failed to persist sync map: {path}") from exc


def load_sync_map(*, config: PlanPilotConfig, plan_id: str) -> SyncMap:
    path = config.sync_path
    if not path.exists():
        return SyncMap(plan_id=plan_id, target=config.target, board_url=config.board_url, entries={})
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
        parsed = SyncMap.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ConfigError(f"invalid sync map file: {path}") from exc
    return parsed
