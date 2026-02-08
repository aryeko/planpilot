from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def slice_epics_for_sync(epics_path: Path, stories_path: Path, tasks_path: Path, out_dir: Path) -> None:
    epics = _read_json(epics_path)
    stories = _read_json(stories_path)
    tasks = _read_json(tasks_path)

    stories_by_id = {s["id"]: s for s in stories}

    for epic in epics:
        eid = epic["id"]
        story_ids = epic.get("story_ids", [])
        epic_stories = [stories_by_id[sid] for sid in story_ids if sid in stories_by_id]
        epic_story_ids = {s["id"] for s in epic_stories}

        epic_tasks = [dict(t) for t in tasks if t.get("story_id") in epic_story_ids]
        epic_task_ids = {t["id"] for t in epic_tasks}
        for task in epic_tasks:
            deps = task.get("depends_on") or []
            task["depends_on"] = [dep for dep in deps if dep in epic_task_ids]

        _write_json(out_dir / f"epics.{eid}.json", [epic])
        _write_json(out_dir / f"stories.{eid}.json", epic_stories)
        _write_json(out_dir / f"tasks.{eid}.json", epic_tasks)
