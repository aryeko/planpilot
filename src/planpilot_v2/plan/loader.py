"""Plan loading from JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from planpilot_v2.contracts.config import PlanPaths
from planpilot_v2.contracts.exceptions import PlanLoadError
from planpilot_v2.contracts.plan import Plan, PlanItemType


class PlanLoader:
    """Load plan JSON files into Plan contracts."""

    def load(self, plan_paths: PlanPaths) -> Plan:
        try:
            if plan_paths.unified is not None:
                items_payload = self._load_unified(plan_paths.unified)
            else:
                items_payload = self._load_split(plan_paths)
            return Plan(items=items_payload)
        except PlanLoadError:
            raise
        except ValidationError as exc:
            raise PlanLoadError(f"plan schema mismatch: {exc}") from exc

    def _load_unified(self, path: Path) -> list[dict[str, Any]]:
        payload = self._read_json(path)
        if not isinstance(payload, dict):
            raise PlanLoadError(f"unified plan root must be an object: {path}")
        items = payload.get("items")
        if not isinstance(items, list):
            raise PlanLoadError(f"unified plan must contain an 'items' array: {path}")
        return [self._expect_object(item, path=path) for item in items]

    def _load_split(self, plan_paths: PlanPaths) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        role_to_path: list[tuple[PlanItemType, Path | None]] = [
            (PlanItemType.EPIC, plan_paths.epics),
            (PlanItemType.STORY, plan_paths.stories),
            (PlanItemType.TASK, plan_paths.tasks),
        ]
        for item_type, path in role_to_path:
            if path is None:
                continue
            payload = self._read_json(path)
            if not isinstance(payload, list):
                raise PlanLoadError(f"split plan file must contain a JSON array: {path}")
            for raw_item in payload:
                item = self._expect_object(raw_item, path=path)
                item["type"] = item_type.value
                items.append(item)
        return items

    def _read_json(self, path: Path) -> Any:
        if not path.exists():
            raise PlanLoadError(f"plan file not found: {path}")
        if not path.is_file():
            raise PlanLoadError(f"plan path is not a file: {path}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise PlanLoadError(f"failed reading plan file: {path}") from exc
        except json.JSONDecodeError as exc:
            raise PlanLoadError(f"invalid JSON in plan file: {path}") from exc

    @staticmethod
    def _expect_object(value: Any, *, path: Path) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise PlanLoadError(f"plan item must be a JSON object: {path}")
        return dict(value)
