"""Deterministic plan hashing."""

from __future__ import annotations

import hashlib
import json

from planpilot.models.plan import Plan


def compute_plan_id(plan: Plan) -> str:
    """Compute a deterministic 12-char hex plan ID.

    The ID is derived from a SHA-256 hash of the canonically-serialized plan.
    """
    data = {
        "epics": [e.model_dump(mode="json", by_alias=True) for e in plan.epics],
        "stories": [s.model_dump(mode="json", by_alias=True) for s in plan.stories],
        "tasks": [t.model_dump(mode="json", by_alias=True) for t in plan.tasks],
    }
    norm = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:12]
