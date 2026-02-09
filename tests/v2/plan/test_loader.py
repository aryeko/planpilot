from __future__ import annotations

import json

import pytest

from planpilot_v2.contracts.config import PlanPaths
from planpilot_v2.contracts.exceptions import PlanLoadError
from planpilot_v2.contracts.plan import PlanItemType
from planpilot_v2.plan.loader import PlanLoader


def test_load_unified_plan(tmp_path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "E1",
                        "type": "EPIC",
                        "title": "Epic",
                        "goal": "Goal",
                        "requirements": ["R1"],
                        "acceptance_criteria": ["AC1"],
                    }
                ]
            }
        )
    )

    plan = PlanLoader().load(PlanPaths(unified=plan_path))

    assert len(plan.items) == 1
    assert plan.items[0].id == "E1"
    assert plan.items[0].type is PlanItemType.EPIC


def test_load_split_plan_assigns_type_by_file_role(tmp_path) -> None:
    epics_path = tmp_path / "epics.json"
    stories_path = tmp_path / "stories.json"
    tasks_path = tmp_path / "tasks.json"

    epics_path.write_text(
        json.dumps(
            [
                {
                    "id": "E1",
                    "title": "Epic",
                    "goal": "Goal",
                    "requirements": ["R1"],
                    "acceptance_criteria": ["AC1"],
                }
            ]
        )
    )
    stories_path.write_text(
        json.dumps(
            [
                {
                    "id": "S1",
                    "title": "Story",
                    "goal": "Goal",
                    "parent_id": "E1",
                    "requirements": ["R1"],
                    "acceptance_criteria": ["AC1"],
                }
            ]
        )
    )
    tasks_path.write_text(
        json.dumps(
            [
                {
                    "id": "T1",
                    "title": "Task",
                    "goal": "Goal",
                    "parent_id": "S1",
                    "requirements": ["R1"],
                    "acceptance_criteria": ["AC1"],
                }
            ]
        )
    )

    plan = PlanLoader().load(PlanPaths(epics=epics_path, stories=stories_path, tasks=tasks_path))

    assert [item.type for item in plan.items] == [PlanItemType.EPIC, PlanItemType.STORY, PlanItemType.TASK]


def test_missing_file_raises_plan_load_error(tmp_path) -> None:
    missing_path = tmp_path / "missing.json"

    with pytest.raises(PlanLoadError):
        PlanLoader().load(PlanPaths(unified=missing_path))


def test_invalid_json_raises_plan_load_error(tmp_path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text("{not valid json")

    with pytest.raises(PlanLoadError):
        PlanLoader().load(PlanPaths(unified=plan_path))


def test_load_empty_plan(tmp_path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({"items": []}))

    plan = PlanLoader().load(PlanPaths(unified=plan_path))

    assert plan.items == []
