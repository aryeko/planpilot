import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from planpilot.sync import run_sync
from planpilot.types import SyncConfig


def _write_json(path: Path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


class TestSyncPreflight(unittest.TestCase):
    def test_missing_input_file_fails_fast(self):
        cfg = SyncConfig(
            repo="owner/repo",
            project_url="https://github.com/orgs/o/projects/1",
            epics_path="missing-epics.json",
            stories_path="missing-stories.json",
            tasks_path="missing-tasks.json",
            sync_path="sync.json",
            label="codex",
            status="Backlog",
            priority="P1",
            iteration="active",
            size_field="Size",
            size_from_tshirt=True,
            dry_run=True,
        )
        with self.assertRaises(RuntimeError) as ctx:
            run_sync(cfg)
        self.assertIn("missing required file", str(ctx.exception))

    def test_auth_failure_reports_actionable_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            epics = root / "epics.json"
            stories = root / "stories.json"
            tasks = root / "tasks.json"
            sync_path = root / "sync.json"
            _write_json(
                epics,
                [
                    {
                        "id": "E-1",
                        "title": "Epic",
                        "story_ids": ["S-1"],
                        "goal": "g",
                        "spec_ref": {"path": "p", "section": "s"},
                    }
                ],
            )
            _write_json(
                stories,
                [
                    {
                        "id": "S-1",
                        "epic_id": "E-1",
                        "title": "Story",
                        "task_ids": ["T-1"],
                        "goal": "g",
                        "spec_ref": {"path": "p", "section": "s"},
                    }
                ],
            )
            _write_json(
                tasks,
                [
                    {
                        "id": "T-1",
                        "story_id": "S-1",
                        "title": "Task",
                        "motivation": "m",
                        "spec_ref": {"path": "p", "section": "s"},
                        "requirements": [],
                        "acceptance_criteria": [],
                        "verification": {},
                        "artifacts": [],
                        "depends_on": [],
                    }
                ],
            )

            cfg = SyncConfig(
                repo="owner/repo",
                project_url="https://github.com/orgs/o/projects/1",
                epics_path=str(epics),
                stories_path=str(stories),
                tasks_path=str(tasks),
                sync_path=str(sync_path),
                label="codex",
                status="Backlog",
                priority="P1",
                iteration="active",
                size_field="Size",
                size_from_tshirt=True,
                dry_run=True,
            )

            auth_result = mock.Mock(returncode=1)
            with (
                mock.patch("planpilot.sync.gh_run", return_value=auth_result),
                self.assertRaises(RuntimeError) as ctx,
            ):
                run_sync(cfg)
            self.assertIn("gh auth login", str(ctx.exception))

    def _make_valid_plan(self, root):
        """Return (epics_path, stories_path, tasks_path) with a valid minimal plan."""
        epics = root / "epics.json"
        stories = root / "stories.json"
        tasks = root / "tasks.json"
        _write_json(
            epics,
            [
                {"id": "E-1", "title": "Epic", "story_ids": ["S-1"], "goal": "g", "spec_ref": "s"},
            ],
        )
        _write_json(
            stories,
            [
                {"id": "S-1", "epic_id": "E-1", "title": "Story", "task_ids": ["T-1"], "goal": "g", "spec_ref": "s"},
            ],
        )
        _write_json(
            tasks,
            [
                {
                    "id": "T-1",
                    "story_id": "S-1",
                    "title": "Task",
                    "motivation": "m",
                    "spec_ref": "s",
                    "requirements": [],
                    "acceptance_criteria": [],
                    "verification": {},
                    "artifacts": [],
                    "depends_on": [],
                },
            ],
        )
        return epics, stories, tasks

    def _make_config(self, epics, stories, tasks, sync_path):
        return SyncConfig(
            repo="owner/repo",
            project_url="https://github.com/orgs/o/projects/1",
            epics_path=str(epics),
            stories_path=str(stories),
            tasks_path=str(tasks),
            sync_path=str(sync_path),
            label="codex",
            status="Backlog",
            priority="P1",
            iteration="active",
            size_field="Size",
            size_from_tshirt=True,
            dry_run=True,
        )

    def test_missing_required_field_on_epic(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            epics, stories, tasks = self._make_valid_plan(root)
            # Remove 'goal' from epic
            _write_json(epics, [{"id": "E-1", "title": "Epic", "story_ids": ["S-1"], "spec_ref": "s"}])
            cfg = self._make_config(epics, stories, tasks, root / "sync.json")
            with self.assertRaises(RuntimeError) as ctx:
                run_sync(cfg)
            self.assertIn("missing required field 'goal'", str(ctx.exception))

    def test_missing_required_field_on_story(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            epics, stories, tasks = self._make_valid_plan(root)
            # Remove 'epic_id' from story
            _write_json(stories, [{"id": "S-1", "title": "Story", "task_ids": ["T-1"], "goal": "g", "spec_ref": "s"}])
            cfg = self._make_config(epics, stories, tasks, root / "sync.json")
            with self.assertRaises(RuntimeError) as ctx:
                run_sync(cfg)
            self.assertIn("missing required field 'epic_id'", str(ctx.exception))

    def test_missing_required_field_on_task(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            epics, stories, tasks = self._make_valid_plan(root)
            # Remove 'motivation' and 'depends_on' from task
            _write_json(
                tasks,
                [
                    {
                        "id": "T-1",
                        "story_id": "S-1",
                        "title": "Task",
                        "spec_ref": "s",
                        "requirements": [],
                        "acceptance_criteria": [],
                        "verification": {},
                        "artifacts": [],
                    },
                ],
            )
            cfg = self._make_config(epics, stories, tasks, root / "sync.json")
            with self.assertRaises(RuntimeError) as ctx:
                run_sync(cfg)
            error_msg = str(ctx.exception)
            self.assertIn("missing required field 'motivation'", error_msg)
            self.assertIn("missing required field 'depends_on'", error_msg)

    def test_story_missing_task_ids_field(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            epics, stories, tasks = self._make_valid_plan(root)
            # Remove 'task_ids' from story
            _write_json(
                stories,
                [
                    {"id": "S-1", "epic_id": "E-1", "title": "Story", "goal": "g", "spec_ref": "s"},
                ],
            )
            cfg = self._make_config(epics, stories, tasks, root / "sync.json")
            with self.assertRaises(RuntimeError) as ctx:
                run_sync(cfg)
            self.assertIn("missing required field 'task_ids'", str(ctx.exception))

    def test_epic_missing_story_ids_field(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            epics, stories, tasks = self._make_valid_plan(root)
            # Remove 'story_ids' from epic
            _write_json(epics, [{"id": "E-1", "title": "Epic", "goal": "g", "spec_ref": "s"}])
            cfg = self._make_config(epics, stories, tasks, root / "sync.json")
            with self.assertRaises(RuntimeError) as ctx:
                run_sync(cfg)
            self.assertIn("missing required field 'story_ids'", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
