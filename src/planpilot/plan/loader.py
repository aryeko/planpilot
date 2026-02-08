"""Load a Plan from JSON files on disk."""

from __future__ import annotations

import json
from pathlib import Path

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
        RuntimeError: If any file is missing or contains invalid JSON.
        pydantic.ValidationError: If the data doesn't match the schema.
    """
    # Check files exist
    for p in (epics_path, stories_path, tasks_path):
        if not p.exists():
            raise RuntimeError(f"missing required file: {p}")
    # Load JSON
    try:
        epics = json.loads(epics_path.read_text(encoding="utf-8"))
        stories = json.loads(stories_path.read_text(encoding="utf-8"))
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON input: {exc}") from exc

    return Plan(epics=epics, stories=stories, tasks=tasks)
