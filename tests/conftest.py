from pathlib import Path

import pytest

from planpilot.contracts.config import PlanPaths, PlanPilotConfig
from planpilot.contracts.plan import Plan, PlanItem, PlanItemType


@pytest.fixture
def sample_epic() -> PlanItem:
    return PlanItem(
        id="E1",
        type=PlanItemType.EPIC,
        title="Epic One",
        goal="Deliver feature X",
        requirements=["R1"],
        acceptance_criteria=["AC1"],
        sub_item_ids=["S1"],
    )


@pytest.fixture
def sample_story() -> PlanItem:
    return PlanItem(
        id="S1",
        type=PlanItemType.STORY,
        title="Story One",
        goal="Implement part A",
        parent_id="E1",
        requirements=["R1"],
        acceptance_criteria=["AC1"],
        sub_item_ids=["T1"],
    )


@pytest.fixture
def sample_task() -> PlanItem:
    return PlanItem(
        id="T1",
        type=PlanItemType.TASK,
        title="Task One",
        goal="Code module A",
        parent_id="S1",
        requirements=["R1"],
        acceptance_criteria=["AC1"],
    )


@pytest.fixture
def sample_plan(sample_epic: PlanItem, sample_story: PlanItem, sample_task: PlanItem) -> Plan:
    return Plan(items=[sample_epic, sample_story, sample_task])


@pytest.fixture
def sample_config(tmp_path: Path) -> PlanPilotConfig:
    return PlanPilotConfig(
        provider="github",
        target="owner/repo",
        board_url="https://github.com/orgs/owner/projects/1",
        plan_paths=PlanPaths(unified=tmp_path / "plan.json"),
        sync_path=tmp_path / "sync-map.json",
    )
