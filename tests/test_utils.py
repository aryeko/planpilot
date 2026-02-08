import unittest

from planpilot import utils


class TestUtils(unittest.TestCase):
    def test_parse_markers(self):
        body = """\
<!-- PLAN_ID: 1234567890ab -->

<!-- EPIC_ID: E-TEST-001 -->

<!-- STORY_ID: S-TEST-001 -->

<!-- TASK_ID: T-TEST-001 -->
"""
        markers = utils.parse_markers(body)
        self.assertEqual(markers["plan_id"], "1234567890ab")
        self.assertEqual(markers["epic_id"], "E-TEST-001")
        self.assertEqual(markers["story_id"], "S-TEST-001")
        self.assertEqual(markers["task_id"], "T-TEST-001")

    def test_build_issue_mapping_plan_filter(self):
        issues = [
            {"id": "I1", "number": 1, "body": "<!-- PLAN_ID: 123 -->\n<!-- EPIC_ID: E-1 -->"},
            {"id": "I2", "number": 2, "body": "<!-- PLAN_ID: 999 -->\n<!-- STORY_ID: S-1 -->"},
            {"id": "I3", "number": 3, "body": "<!-- PLAN_ID: 123 -->\n<!-- TASK_ID: T-1 -->"},
        ]
        mapping = utils.build_issue_mapping(issues, plan_id="123")
        self.assertIn("E-1", mapping["epics"])
        self.assertNotIn("S-1", mapping["stories"])
        self.assertIn("T-1", mapping["tasks"])

    def test_build_issue_search_query(self):
        query = utils.build_issue_search_query("bookmd/getvim", "abc123")
        self.assertIn("repo:bookmd/getvim", query)
        self.assertIn("PLAN_ID: abc123", query)

    def test_build_create_issue_input(self):
        payload = utils.build_create_issue_input("REPO1", "Title", "Body", ["L1"])
        self.assertEqual(payload["repositoryId"], "REPO1")
        self.assertEqual(payload["title"], "Title")
        self.assertEqual(payload["body"], "Body")
        self.assertEqual(payload["labelIds"], ["L1"])

    def test_project_item_map(self):
        items = [
            {"id": "ITEM1", "content": {"id": "ISSUE1"}},
            {"id": "ITEM2", "content": {"id": "ISSUE2"}},
        ]
        cache = utils.build_project_item_map(items)
        self.assertEqual(utils.get_project_item_id("ISSUE1", cache), "ITEM1")
        self.assertIsNone(utils.get_project_item_id("MISSING", cache))

    def test_task_dependencies_block(self):
        block = utils.build_task_dependencies_block({"T2": "#2"})
        self.assertIn("#2", block)

    def test_epic_stories_section(self):
        section = utils.build_epic_stories_section([(12, "Story one")])
        self.assertIn("#12", section)

    def test_story_tasks_section(self):
        section = utils.build_story_tasks_section([(22, "Task one")])
        self.assertIn("#22", section)

    def test_parent_map(self):
        nodes = [
            {"id": "S1", "parent": {"id": "E1"}},
            {"id": "S2", "parent": None},
        ]
        mapping = utils.build_parent_map(nodes)
        self.assertEqual(mapping["S1"], "E1")
        self.assertIsNone(mapping["S2"])

    def test_blocked_by_map(self):
        nodes = [
            {"id": "S1", "blockedBy": {"nodes": [{"id": "S2"}]}},
            {"id": "S2", "blockedBy": {"nodes": []}},
        ]
        mapping = utils.build_blocked_by_map(nodes)
        self.assertEqual(mapping["S1"], {"S2"})
        self.assertEqual(mapping["S2"], set())

    def test_resolve_option_id(self):
        options = [{"id": "1", "name": "P0"}, {"id": "2", "name": "P1"}]
        self.assertEqual(utils.resolve_option_id(options, "P1"), "2")
        self.assertIsNone(utils.resolve_option_id(options, "P2"))


if __name__ == "__main__":
    unittest.main()
