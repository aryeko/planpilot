"""Sync-map persistence helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from planpilot.contracts.exceptions import ConfigError, SyncError
from planpilot.contracts.sync import SyncMap


def output_sync_path(*, sync_path: Path, dry_run: bool) -> Path:
    if not dry_run:
        return sync_path
    return Path(f"{sync_path}.dry-run")


def persist_sync_map(*, sync_map: SyncMap, sync_path: Path, dry_run: bool) -> None:
    path = output_sync_path(sync_path=sync_path, dry_run=dry_run)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(sync_map.model_dump_json(indent=2), encoding="utf-8")
    except OSError as exc:
        raise SyncError(f"failed to persist sync map: {path}") from exc


def load_sync_map(*, sync_path: Path, plan_id: str, target: str, board_url: str) -> SyncMap:
    if not sync_path.exists():
        return SyncMap(plan_id=plan_id, target=target, board_url=board_url, entries={})
    try:
        payload: Any = json.loads(sync_path.read_text(encoding="utf-8"))
        return SyncMap.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ConfigError(f"invalid sync map file: {sync_path}") from exc
