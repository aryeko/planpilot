#!/usr/bin/env python3
"""
Create per-epic .plans slices for planpilot.

DEPRECATED: prefer native `planpilot` multi-epic sync. Use `planpilot-slice`
only for manual per-epic workflows.

Why this exists:
- Some teams prefer explicit per-epic sync files.
- This helper emits one epics/stories/tasks JSON triplet per epic.
- Task depends_on is filtered to local slice task IDs to keep validation closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

_SAFE_FILENAME_FRAGMENT = re.compile(r"[^A-Za-z0-9._-]+")


def load_json(path: Path) -> Any:
    """Load and parse a JSON file from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    """Write JSON with stable formatting and a trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def safe_epic_id_for_filename(value: object) -> str:
    """Return a filesystem-safe epic id fragment for output filenames."""
    raw = "" if value is None else str(value).strip()
    cleaned = _SAFE_FILENAME_FRAGMENT.sub("_", raw)
    cleaned = cleaned.strip("._-")
    if cleaned:
        return cleaned

    token = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"epic_{token}"


def build_slices(epics_path: Path, stories_path: Path, tasks_path: Path, out_dir: Path) -> None:
    """Emit one epics/stories/tasks JSON slice per epic."""
    epics = load_json(epics_path)
    stories = load_json(stories_path)
    tasks = load_json(tasks_path)

    stories_by_id = {s["id"]: s for s in stories}

    for index, epic in enumerate(epics):
        if not isinstance(epic, dict):
            raise ValueError(f"Epic at index {index} must be an object: {epic!r}")

        for field in ("id", "story_ids"):
            if field not in epic:
                raise ValueError(f"Epic at index {index} missing required '{field}': {epic!r}")

        eid = epic["id"]
        file_eid = safe_epic_id_for_filename(eid)
        story_ids = epic["story_ids"]
        epic_stories = [stories_by_id[sid] for sid in story_ids if sid in stories_by_id]
        epic_story_set = {s["id"] for s in epic_stories}

        epic_tasks = [dict(t) for t in tasks if t["story_id"] in epic_story_set]
        epic_task_ids = {t["id"] for t in epic_tasks}

        for t in epic_tasks:
            deps = t.get("depends_on", [])
            t["depends_on"] = [d for d in deps if d in epic_task_ids]

        write_json(out_dir / f"epics.{file_eid}.json", [epic])
        write_json(out_dir / f"stories.{file_eid}.json", epic_stories)
        write_json(out_dir / f"tasks.{file_eid}.json", epic_tasks)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for per-epic slicing."""
    p = argparse.ArgumentParser(description="Slice .plans JSON into per-epic sync-ready files")
    p.add_argument("--epics-path", required=True, help="Path to .plans/epics.json")
    p.add_argument("--stories-path", required=True, help="Path to .plans/stories.json")
    p.add_argument("--tasks-path", required=True, help="Path to .plans/tasks.json")
    p.add_argument("--out-dir", default=".plans/tmp", help="Output directory for per-epic slices")
    return p.parse_args()


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    build_slices(
        epics_path=Path(args.epics_path),
        stories_path=Path(args.stories_path),
        tasks_path=Path(args.tasks_path),
        out_dir=Path(args.out_dir),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
