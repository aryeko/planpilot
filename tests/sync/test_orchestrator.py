"""Tests for MultiEpicOrchestrator."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from planpilot.config import SyncConfig
from planpilot.models.sync import SyncEntry, SyncMap, SyncResult
from planpilot.sync.orchestrator import MultiEpicOrchestrator


def _write_plan_files(root: Path, epics: list[dict[str, object]]) -> tuple[Path, Path, Path]:
    epics_path = root / "epics.json"
    stories_path = root / "stories.json"
    tasks_path = root / "tasks.json"

    stories: list[dict[str, object]] = []
    tasks: list[dict[str, object]] = []
    for epic in epics:
        for story_id in epic["story_ids"]:  # type: ignore[index]
            stories.append(
                {
                    "id": story_id,
                    "epic_id": epic["id"],
                    "title": str(story_id),
                    "goal": "goal",
                    "spec_ref": "spec.md",
                    "task_ids": [f"T-{story_id}"],
                }
            )
            tasks.append(
                {
                    "id": f"T-{story_id}",
                    "story_id": story_id,
                    "title": f"Task {story_id}",
                    "motivation": "m",
                    "spec_ref": "spec.md",
                    "requirements": [],
                    "acceptance_criteria": [],
                    "artifacts": [],
                    "depends_on": [],
                }
            )

    epics_path.write_text(json.dumps(epics), encoding="utf-8")
    stories_path.write_text(json.dumps(stories), encoding="utf-8")
    tasks_path.write_text(json.dumps(tasks), encoding="utf-8")
    return epics_path, stories_path, tasks_path


@pytest.mark.asyncio
async def test_sync_all_single_epic_passthrough(tmp_path: Path) -> None:
    epics_path, stories_path, tasks_path = _write_plan_files(
        tmp_path,
        [{"id": "E-1", "story_ids": ["S-1"]}],
    )
    config = SyncConfig(
        repo="owner/repo",
        project_url="https://github.com/orgs/o/projects/1",
        epics_path=epics_path,
        stories_path=stories_path,
        tasks_path=tasks_path,
        sync_path=tmp_path / "sync.json",
        dry_run=True,
    )

    expected = SyncResult(
        sync_map=SyncMap(plan_id="single", repo=config.repo, project_url=config.project_url),
        epics_created=1,
        stories_created=1,
        tasks_created=1,
        dry_run=True,
    )
    engine_instance = AsyncMock()
    engine_instance.sync = AsyncMock(return_value=expected)

    with (
        patch("planpilot.sync.orchestrator.SyncEngine", return_value=engine_instance) as engine_cls,
        patch("planpilot.sync.orchestrator.slice_epics_for_sync") as slicer,
    ):
        orchestrator = MultiEpicOrchestrator(provider=AsyncMock(), renderer=AsyncMock(), config=config)
        result = await orchestrator.sync_all()

    assert result == expected
    slicer.assert_not_called()
    engine_cls.assert_called_once()
    engine_instance.sync.assert_called_once()


@pytest.mark.asyncio
async def test_sync_all_multi_epic_merges_and_writes_outputs(tmp_path: Path) -> None:
    epics_path, stories_path, tasks_path = _write_plan_files(
        tmp_path,
        [
            {"id": "E-1", "story_ids": ["S-1"]},
            {"id": "E/2", "story_ids": ["S-2"]},
        ],
    )
    sync_path = tmp_path / "sync-map.json"
    config = SyncConfig(
        repo="owner/repo",
        project_url="https://github.com/orgs/o/projects/1",
        epics_path=epics_path,
        stories_path=stories_path,
        tasks_path=tasks_path,
        sync_path=sync_path,
        dry_run=True,
    )

    class FakeEngine:
        def __init__(self, provider: object, renderer: object, config: SyncConfig) -> None:
            self._config = config

        async def sync(self) -> SyncResult:
            epic_payload = json.loads(Path(self._config.epics_path).read_text(encoding="utf-8"))
            epic_id = epic_payload[0]["id"]
            story_id = f"S-{epic_id}"
            task_id = f"T-{epic_id}"
            sync_map = SyncMap(
                plan_id=f"plan-{epic_id}",
                repo=self._config.repo,
                project_url=self._config.project_url,
                epics={epic_id: SyncEntry(issue_number=1, url="u", node_id=f"n-{epic_id}")},
                stories={story_id: SyncEntry(issue_number=2, url="u", node_id=f"n-{story_id}")},
                tasks={task_id: SyncEntry(issue_number=3, url="u", node_id=f"n-{task_id}")},
            )
            return SyncResult(sync_map=sync_map, epics_created=1, stories_created=1, tasks_created=1, dry_run=True)

    with patch("planpilot.sync.orchestrator.SyncEngine", FakeEngine):
        orchestrator = MultiEpicOrchestrator(provider=AsyncMock(), renderer=AsyncMock(), config=config)
        result = await orchestrator.sync_all()

    assert result.dry_run is True
    assert result.epics_created == 2
    assert result.stories_created == 2
    assert result.tasks_created == 2
    assert set(result.sync_map.epics) == {"E-1", "E/2"}
    assert sync_path.exists()
    assert (tmp_path / "sync-map.E-1.json").exists()
    assert (tmp_path / "sync-map.E_2.json").exists()
