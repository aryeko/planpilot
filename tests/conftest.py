"""Shared test fixtures for planpilot tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from planpilot.config import SyncConfig
from planpilot.models.plan import Epic, Plan, Story, Task, Verification


@pytest.fixture
def sample_epic() -> Epic:
    """A minimal valid Epic."""
    return Epic(
        id="E-1",
        title="Test Epic",
        goal="Test goal",
        spec_ref="spec.md",
        story_ids=["S-1"],
    )


@pytest.fixture
def sample_story() -> Story:
    """A minimal valid Story."""
    return Story(
        id="S-1",
        epic_id="E-1",
        title="Test Story",
        goal="Story goal",
        spec_ref="spec.md",
        task_ids=["T-1"],
    )


@pytest.fixture
def sample_task() -> Task:
    """A minimal valid Task."""
    return Task(
        id="T-1",
        story_id="S-1",
        title="Test Task",
        motivation="Task motivation",
        spec_ref="spec.md",
        requirements=["req1"],
        acceptance_criteria=["ac1"],
        verification=Verification(),
        artifacts=["artifact1"],
        depends_on=[],
    )


@pytest.fixture
def sample_plan(sample_epic: Epic, sample_story: Story, sample_task: Task) -> Plan:
    """A minimal valid Plan with one epic, one story, one task."""
    return Plan(epics=[sample_epic], stories=[sample_story], tasks=[sample_task])


@pytest.fixture
def plan_json_files(
    tmp_path: Path, sample_epic: Epic, sample_story: Story, sample_task: Task
) -> tuple[Path, Path, Path]:
    """Write sample plan to JSON files and return (epics_path, stories_path, tasks_path)."""
    epics_path = tmp_path / "epics.json"
    stories_path = tmp_path / "stories.json"
    tasks_path = tmp_path / "tasks.json"
    epics_path.write_text(json.dumps([sample_epic.model_dump(mode="json", by_alias=True)]), encoding="utf-8")
    stories_path.write_text(json.dumps([sample_story.model_dump(mode="json", by_alias=True)]), encoding="utf-8")
    tasks_path.write_text(json.dumps([sample_task.model_dump(mode="json", by_alias=True)]), encoding="utf-8")
    return epics_path, stories_path, tasks_path


@pytest.fixture
def sample_config(tmp_path: Path) -> SyncConfig:
    """A minimal valid SyncConfig."""
    return SyncConfig(
        repo="owner/repo",
        project_url="https://github.com/orgs/myorg/projects/1",
        epics_path=tmp_path / "epics.json",
        stories_path=tmp_path / "stories.json",
        tasks_path=tmp_path / "tasks.json",
        sync_path=tmp_path / "sync.json",
    )
