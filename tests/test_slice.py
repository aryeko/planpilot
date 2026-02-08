import json
import tempfile
import unittest
from pathlib import Path

from planpilot.slice import slice_epics_for_sync


class TestSliceEpicsForSync(unittest.TestCase):
    def test_slice_filters_cross_epic_dependencies(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            epics_path = root / "epics.json"
            stories_path = root / "stories.json"
            tasks_path = root / "tasks.json"
            out_dir = root / "tmp"

            epics = [
                {"id": "E-1", "story_ids": ["S-1"]},
                {"id": "E-2", "story_ids": ["S-2"]},
            ]
            stories = [
                {"id": "S-1", "epic_id": "E-1", "task_ids": ["T-1"]},
                {"id": "S-2", "epic_id": "E-2", "task_ids": ["T-2"]},
            ]
            tasks = [
                {"id": "T-1", "story_id": "S-1", "depends_on": ["T-2"]},
                {"id": "T-2", "story_id": "S-2", "depends_on": []},
            ]

            epics_path.write_text(json.dumps(epics), encoding="utf-8")
            stories_path.write_text(json.dumps(stories), encoding="utf-8")
            tasks_path.write_text(json.dumps(tasks), encoding="utf-8")

            slice_epics_for_sync(epics_path, stories_path, tasks_path, out_dir)

            e1_tasks = json.loads((out_dir / "tasks.E-1.json").read_text(encoding="utf-8"))
            self.assertEqual(e1_tasks[0]["depends_on"], [])


if __name__ == "__main__":
    unittest.main()
