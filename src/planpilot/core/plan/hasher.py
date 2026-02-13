"""Deterministic plan hashing."""

from __future__ import annotations

import hashlib
import json
from typing import Any, cast

from planpilot.core.contracts.plan import Plan, PlanItem


class PlanHasher:
    """Compute deterministic plan identity."""

    def compute_plan_id(self, plan: Plan) -> str:
        sorted_items = sorted(plan.items, key=lambda item: (item.type.value, item.id))
        payload = [self._canonical_item(item) for item in sorted_items]
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]

    def _canonical_item(self, item: PlanItem) -> dict[str, Any]:
        dumped = cast(dict[str, Any], item.model_dump(mode="json", by_alias=True, exclude_none=True))
        return cast(dict[str, Any], self._drop_empty_containers(dumped))

    def _drop_empty_containers(self, value: Any) -> Any:
        if isinstance(value, list):
            normalized_list = [self._drop_empty_containers(item) for item in value]
            return [item for item in normalized_list if item not in ({}, [])]
        if isinstance(value, dict):
            normalized_dict = {k: self._drop_empty_containers(v) for k, v in value.items()}
            return {k: v for k, v in normalized_dict.items() if v not in ({}, [])}
        return value
