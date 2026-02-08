from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def slice_epics_for_sync(epics_path: Path, stories_path: Path, tasks_path: Path, out_dir: Path) -> None:
    """Slice plan files into per-epic sync inputs.

    Reads epics, stories, and tasks JSON files and writes per-epic slices
    to the output directory. Filters cross-epic dependencies from tasks.

    Args:
        epics_path: Path to epics.json file.
        stories_path: Path to stories.json file.
        tasks_path: Path to tasks.json file.
        out_dir: Output directory for per-epic slice files.
    """
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


def _build_slice_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Slice .plans files into per-epic sync inputs")
    parser.add_argument("--epics-path", required=True, help="Path to epics.json")
    parser.add_argument("--stories-path", required=True, help="Path to stories.json")
    parser.add_argument("--tasks-path", required=True, help="Path to tasks.json")
    parser.add_argument("--out-dir", default=".plans/tmp", help="Output directory for per-epic slices")
    return parser


def slice_cli() -> int:
    """CLI entry point for the planpilot-slice command."""
    args = _build_slice_parser().parse_args()
    try:
        slice_epics_for_sync(
            epics_path=Path(args.epics_path),
            stories_path=Path(args.stories_path),
            tasks_path=Path(args.tasks_path),
            out_dir=Path(args.out_dir),
        )
        return 0
    except FileNotFoundError as e:
        print(f"Error: File not found: {e.filename}", file=sys.stderr)
        return 1
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"Error: Invalid input format: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(slice_cli())
