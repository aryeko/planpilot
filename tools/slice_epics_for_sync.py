#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from plan_gh_project_sync.slice import slice_epics_for_sync


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Slice .plans files into per-epic sync inputs")
    parser.add_argument("--epics-path", required=True)
    parser.add_argument("--stories-path", required=True)
    parser.add_argument("--tasks-path", required=True)
    parser.add_argument("--out-dir", default=".plans/tmp")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    slice_epics_for_sync(
        epics_path=Path(args.epics_path),
        stories_path=Path(args.stories_path),
        tasks_path=Path(args.tasks_path),
        out_dir=Path(args.out_dir),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
