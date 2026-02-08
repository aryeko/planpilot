import unittest
from unittest import mock

from plan_gh_project_sync import cli


class TestCli(unittest.TestCase):
    def test_parser_requires_mode_flag(self):
        parser = cli.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args([
                "--repo", "owner/repo",
                "--project-url", "https://github.com/orgs/o/projects/1",
                "--epics-path", "epics.json",
                "--stories-path", "stories.json",
                "--tasks-path", "tasks.json",
                "--sync-path", "sync.json",
            ])

    @mock.patch("plan_gh_project_sync.cli.run_sync")
    @mock.patch("sys.argv", [
        "plan-gh-project-sync",
        "--repo", "owner/repo",
        "--project-url", "https://github.com/orgs/o/projects/1",
        "--epics-path", "epics.json",
        "--stories-path", "stories.json",
        "--tasks-path", "tasks.json",
        "--sync-path", "sync.json",
        "--dry-run",
    ])
    def test_main_returns_nonzero_on_runtime_error(self, run_sync_mock):
        run_sync_mock.side_effect = RuntimeError("boom")
        rc = cli.main()
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
