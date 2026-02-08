#!/usr/bin/env python3
"""
Create per-epic .plans slices for plan_gh_project_sync.

Why this exists:
- plan_gh_project_sync currently validates exactly one epic per run.
- This helper emits one epics/stories/tasks JSON triplet per epic.
- Task depends_on is filtered to local slice task IDs to keep validation closed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def build_slices(epics_path: Path, stories_path: Path, tasks_path: Path, out_dir: Path) -> None:
    epics = load_json(epics_path)
    stories = load_json(stories_path)
    tasks = load_json(tasks_path)

    stories_by_id = {s["id"]: s for s in stories}

    for epic in epics:
        eid = epic["id"]
        story_ids = epic.get("story_ids", [])
        epic_stories = [stories_by_id[sid] for sid in story_ids if sid in stories_by_id]
        epic_story_set = {s["id"] for s in epic_stories}

        epic_tasks = [dict(t) for t in tasks if t.get("story_id") in epic_story_set]
        epic_task_ids = {t["id"] for t in epic_tasks}

        for t in epic_tasks:
            deps = t.get("depends_on") or []
            t["depends_on"] = [d for d in deps if d in epic_task_ids]

        write_json(out_dir / f"epics.{eid}.json", [epic])
        write_json(out_dir / f"stories.{eid}.json", epic_stories)
        write_json(out_dir / f"tasks.{eid}.json", epic_tasks)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Slice .plans JSON into per-epic sync-ready files")
    p.add_argument("--epics-path", required=True, help="Path to .plans/epics.json")
    p.add_argument("--stories-path", required=True, help="Path to .plans/stories.json")
    p.add_argument("--tasks-path", required=True, help="Path to .plans/tasks.json")
    p.add_argument("--out-dir", default=".plans/tmp", help="Output directory for per-epic slices")
    return p.parse_args()


def main() -> int:
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
