"""Tests for plan loader."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from planpilot.exceptions import PlanLoadError
from planpilot.models.plan import Plan
from planpilot.plan.loader import load_plan


def test_load_plan_valid_json():
    """Test that load_plan loads valid JSON files into a Plan model."""
    with tempfile.TemporaryDirectory() as tmpdir:
        epics_path = Path(tmpdir) / "epics.json"
        stories_path = Path(tmpdir) / "stories.json"
        tasks_path = Path(tmpdir) / "tasks.json"

        # Create valid plan data
        epics_data = [
            {
                "id": "epic1",
                "title": "Test Epic",
                "goal": "Test goal",
                "spec_ref": "spec.md",
                "story_ids": ["story1"],
                "scope": {"in": [], "out": []},
                "success_metrics": [],
                "risks": [],
                "assumptions": [],
            }
        ]

        stories_data = [
            {
                "id": "story1",
                "epic_id": "epic1",
                "title": "Test Story",
                "goal": "Story goal",
                "spec_ref": "spec.md",
                "task_ids": ["task1"],
                "scope": {"in": [], "out": []},
                "success_metrics": [],
                "risks": [],
                "assumptions": [],
            }
        ]

        tasks_data = [
            {
                "id": "task1",
                "story_id": "story1",
                "title": "Test Task",
                "motivation": "Test motivation",
                "spec_ref": "spec.md",
                "requirements": [],
                "acceptance_criteria": [],
                "verification": {"commands": [], "ci_checks": [], "evidence": [], "manual_steps": []},
                "artifacts": [],
                "depends_on": [],
                "estimate": {"tshirt": "", "hours": None},
                "scope": {"in": [], "out": []},
            }
        ]

        epics_path.write_text(json.dumps(epics_data), encoding="utf-8")
        stories_path.write_text(json.dumps(stories_data), encoding="utf-8")
        tasks_path.write_text(json.dumps(tasks_data), encoding="utf-8")

        plan = load_plan(epics_path, stories_path, tasks_path)

        assert isinstance(plan, Plan)
        assert len(plan.epics) == 1
        assert plan.epics[0].id == "epic1"
        assert len(plan.stories) == 1
        assert plan.stories[0].id == "story1"
        assert len(plan.tasks) == 1
        assert plan.tasks[0].id == "task1"


def test_load_plan_missing_file():
    """Test that load_plan raises PlanLoadError when a file doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        epics_path = Path(tmpdir) / "epics.json"
        stories_path = Path(tmpdir) / "stories.json"
        tasks_path = Path(tmpdir) / "tasks.json"

        # Create only one file
        epics_path.write_text("[]", encoding="utf-8")

        with pytest.raises(PlanLoadError, match="missing required file"):
            load_plan(epics_path, stories_path, tasks_path)


def test_load_plan_invalid_json():
    """Test that load_plan raises PlanLoadError on invalid JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        epics_path = Path(tmpdir) / "epics.json"
        stories_path = Path(tmpdir) / "stories.json"
        tasks_path = Path(tmpdir) / "tasks.json"

        epics_path.write_text("{ invalid json", encoding="utf-8")
        stories_path.write_text("[]", encoding="utf-8")
        tasks_path.write_text("[]", encoding="utf-8")

        with pytest.raises(PlanLoadError, match="invalid JSON input"):
            load_plan(epics_path, stories_path, tasks_path)


def test_load_plan_missing_required_fields():
    """Test that load_plan raises PlanLoadError on missing required fields."""
    from planpilot.exceptions import PlanLoadError

    with tempfile.TemporaryDirectory() as tmpdir:
        epics_path = Path(tmpdir) / "epics.json"
        stories_path = Path(tmpdir) / "stories.json"
        tasks_path = Path(tmpdir) / "tasks.json"

        # Missing required 'id' field in epic
        epics_path.write_text('[{"title": "Test"}]', encoding="utf-8")
        stories_path.write_text("[]", encoding="utf-8")
        tasks_path.write_text("[]", encoding="utf-8")

        with pytest.raises(PlanLoadError, match="plan validation failed"):
            load_plan(epics_path, stories_path, tasks_path)
