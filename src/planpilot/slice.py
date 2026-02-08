from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class SliceResult:
    """Result of slicing a single epic."""

    epic_id: str
    epics_path: Path
    stories_path: Path
    tasks_path: Path
    dropped_deps: list[tuple[str, str]]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _validate_list(data: Any, label: str, required_keys: list[str]) -> list[dict[str, Any]]:
    """Validate that data is a list of dicts with required keys."""
    if not isinstance(data, list):
        raise ValueError(f"{label}: expected a JSON array, got {type(data).__name__}")

    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"{label}[{i}]: expected an object, got {type(item).__name__}")
        for key in required_keys:
            if key not in item:
                raise ValueError(f"{label}[{i}]: missing required key '{key}'")

    return data


def _safe_epic_id(value: str) -> str:
    """Return a filesystem-safe fragment for an epic ID."""
    cleaned = _SAFE_FILENAME_RE.sub("_", value).strip("._-")
    if cleaned:
        return cleaned
    return f"epic_{hashlib.sha1(value.encode('utf-8')).hexdigest()[:12]}"


def slice_epics_for_sync(epics_path: Path, stories_path: Path, tasks_path: Path, out_dir: Path) -> list[SliceResult]:
    """Slice plan files into per-epic sync inputs.

    Reads epics, stories, and tasks JSON files and writes per-epic slices
    to the output directory. Filters cross-epic dependencies from tasks.

    Args:
        epics_path: Path to epics.json file.
        stories_path: Path to stories.json file.
        tasks_path: Path to tasks.json file.
        out_dir: Output directory for per-epic slice files.
    """
    epics = _validate_list(_read_json(epics_path), "epics", ["id", "story_ids"])
    stories = _validate_list(_read_json(stories_path), "stories", ["id", "epic_id"])
    tasks = _validate_list(_read_json(tasks_path), "tasks", ["id", "story_id"])

    results: list[SliceResult] = []

    stories_by_id = {s["id"]: s for s in stories}

    for epic in epics:
        eid = str(epic["id"])
        safe_eid = _safe_epic_id(eid)
        story_ids = epic["story_ids"]
        if not isinstance(story_ids, list):
            raise ValueError(f"epic '{eid}': story_ids must be a list, got {type(story_ids).__name__}")

        epic_stories = [stories_by_id[sid] for sid in story_ids if sid in stories_by_id]
        epic_story_ids = {s["id"] for s in epic_stories}

        epic_tasks = [dict(t) for t in tasks if t.get("story_id") in epic_story_ids]
        epic_task_ids = {t["id"] for t in epic_tasks}
        dropped_deps: list[tuple[str, str]] = []

        for task in epic_tasks:
            deps = task.get("depends_on") or []
            if not isinstance(deps, list):
                raise ValueError(
                    f"task '{task['id']}': depends_on must be a list, got {type(deps).__name__}"
                )

            kept = [dep for dep in deps if dep in epic_task_ids]
            dropped = [dep for dep in deps if dep not in epic_task_ids]
            if dropped:
                logger.warning(
                    "Task %s: dropped %d cross-epic dep(s): %s",
                    task["id"],
                    len(dropped),
                    dropped,
                )
                for dep in dropped:
                    dropped_deps.append((str(task["id"]), str(dep)))
            task["depends_on"] = kept

        epics_out = out_dir / f"epics.{safe_eid}.json"
        stories_out = out_dir / f"stories.{safe_eid}.json"
        tasks_out = out_dir / f"tasks.{safe_eid}.json"

        _write_json(epics_out, [epic])
        _write_json(stories_out, epic_stories)
        _write_json(tasks_out, epic_tasks)

        results.append(
            SliceResult(
                epic_id=eid,
                epics_path=epics_out,
                stories_path=stories_out,
                tasks_path=tasks_out,
                dropped_deps=dropped_deps,
            )
        )

    return results


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
