"""Core helpers for map-sync local state loading."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from planpilot.core.contracts.exceptions import ConfigError
from planpilot.core.contracts.sync import SyncMap


def load_sync_map(*, sync_path: Path, plan_id: str, target: str, board_url: str) -> SyncMap:
    if not sync_path.exists():
        return SyncMap(plan_id=plan_id, target=target, board_url=board_url, entries={})
    try:
        payload: Any = json.loads(sync_path.read_text(encoding="utf-8"))
        return SyncMap.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ConfigError(f"invalid sync map file: {sync_path}") from exc


__all__ = ["load_sync_map"]
