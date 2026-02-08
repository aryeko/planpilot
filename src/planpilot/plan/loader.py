"""Load a Plan from JSON files on disk."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from planpilot.exceptions import PlanLoadError
from planpilot.models.plan import Plan


def load_plan(epics_path: Path, stories_path: Path, tasks_path: Path) -> Plan:
    """Load and parse plan JSON files into a validated Plan model.

    Args:
        epics_path: Path to epics.json.
        stories_path: Path to stories.json.
        tasks_path: Path to tasks.json.

    Returns:
        A validated Plan instance.

    Raises:
        PlanLoadError: If any file is missing, unreadable, contains invalid JSON,
                      or the data doesn't match the schema.
    """
    # Check files exist
    for p in (epics_path, stories_path, tasks_path):
        if not p.exists():
            raise PlanLoadError(f"missing required file: {p}")
    # Load JSON
    try:
        epics = json.loads(epics_path.read_text(encoding="utf-8"))
        stories = json.loads(stories_path.read_text(encoding="utf-8"))
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PlanLoadError(f"invalid JSON input: {exc}") from exc
    except OSError as exc:
        raise PlanLoadError(f"failed to read plan file: {exc}") from exc

    try:
        return Plan(epics=epics, stories=stories, tasks=tasks)
    except ValidationError as exc:
        raise PlanLoadError(f"plan validation failed: {exc}") from exc
