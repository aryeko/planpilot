from __future__ import annotations

import json
from pathlib import Path

import pytest

from planpilot.core.contracts.config import PlanPaths
from planpilot.core.contracts.exceptions import PlanLoadError
from planpilot.core.contracts.plan import PlanItemType
from planpilot.core.plan.loader import PlanLoader


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


def test_unified_root_must_be_object(tmp_path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps([]))

    with pytest.raises(PlanLoadError, match="root must be an object"):
        PlanLoader().load(PlanPaths(unified=plan_path))


def test_unified_items_must_be_array(tmp_path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({"items": {}}))

    with pytest.raises(PlanLoadError, match="must contain an 'items' array"):
        PlanLoader().load(PlanPaths(unified=plan_path))


def test_split_files_must_be_arrays(tmp_path) -> None:
    epics_path = tmp_path / "epics.json"
    epics_path.write_text(json.dumps({"id": "E1"}))

    with pytest.raises(PlanLoadError, match="must contain a JSON array"):
        PlanLoader().load(PlanPaths(epics=epics_path))


def test_split_mode_allows_missing_optional_files(tmp_path) -> None:
    epics_path = tmp_path / "epics.json"
    epics_path.write_text(
        json.dumps([{"id": "E1", "title": "Epic", "goal": "Goal", "requirements": ["R"], "acceptance_criteria": ["A"]}])
    )

    plan = PlanLoader().load(PlanPaths(epics=epics_path))

    assert [item.id for item in plan.items] == ["E1"]


def test_plan_path_must_be_file(tmp_path) -> None:
    plan_dir = tmp_path / "plan-dir"
    plan_dir.mkdir()

    with pytest.raises(PlanLoadError, match="path is not a file"):
        PlanLoader().load(PlanPaths(unified=plan_dir))


def test_plan_item_must_be_json_object(tmp_path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({"items": ["not-an-object"]}))

    with pytest.raises(PlanLoadError, match="plan item must be a JSON object"):
        PlanLoader().load(PlanPaths(unified=plan_path))


def test_schema_validation_errors_wrapped_as_plan_load_error(tmp_path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({"items": [{"id": "E1", "type": "EPIC"}]}))

    with pytest.raises(PlanLoadError, match="schema mismatch"):
        PlanLoader().load(PlanPaths(unified=plan_path))


def test_os_error_is_wrapped_as_plan_load_error(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text("{}")
    original_read_text = Path.read_text

    def _boom(self: Path, *args: object, **kwargs: object) -> str:
        if self == plan_path:
            raise OSError("permission denied")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _boom)

    with pytest.raises(PlanLoadError, match="failed reading plan file"):
        PlanLoader().load(PlanPaths(unified=plan_path))
