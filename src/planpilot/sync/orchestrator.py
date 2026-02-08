"""Multi-epic orchestration built on top of SyncEngine."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from planpilot.config import SyncConfig
from planpilot.models.sync import SyncResult, merge_sync_maps
from planpilot.providers.base import Provider
from planpilot.rendering.base import BodyRenderer
from planpilot.slice import _safe_epic_id, slice_epics_for_sync
from planpilot.sync.engine import SyncEngine


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _per_epic_sync_path(sync_path: Path, epic_id: str) -> Path:
    safe_epic_id = _safe_epic_id(epic_id)
    return sync_path.with_name(f"{sync_path.stem}.{safe_epic_id}.json")


class MultiEpicOrchestrator:
    """Coordinates single/multi-epic sync execution.

    For one epic, delegates directly to SyncEngine.
    For multiple epics, slices inputs, runs per-epic syncs, and merges sync maps.
    """

    def __init__(self, provider: Provider, renderer: BodyRenderer, config: SyncConfig) -> None:
        self._provider = provider
        self._renderer = renderer
        self._config = config

    async def sync_all(self) -> SyncResult:
        epics_data = _read_json(Path(self._config.epics_path))
        epic_count = len(epics_data) if isinstance(epics_data, list) else 0

        if epic_count <= 1:
            engine = SyncEngine(provider=self._provider, renderer=self._renderer, config=self._config)
            return await engine.sync()

        with TemporaryDirectory() as tmp_dir:
            slices = slice_epics_for_sync(
                epics_path=Path(self._config.epics_path),
                stories_path=Path(self._config.stories_path),
                tasks_path=Path(self._config.tasks_path),
                out_dir=Path(tmp_dir),
            )

            per_epic_maps = []
            epics_created = 0
            stories_created = 0
            tasks_created = 0

            for slice_result in slices:
                per_epic_sync_path = _per_epic_sync_path(Path(self._config.sync_path), slice_result.epic_id)
                epic_config = self._config.model_copy(
                    update={
                        "epics_path": slice_result.epics_path,
                        "stories_path": slice_result.stories_path,
                        "tasks_path": slice_result.tasks_path,
                        "sync_path": per_epic_sync_path,
                    }
                )

                engine = SyncEngine(provider=self._provider, renderer=self._renderer, config=epic_config)
                result = await engine.sync()
                per_epic_maps.append(result.sync_map)
                epics_created += result.epics_created
                stories_created += result.stories_created
                tasks_created += result.tasks_created

                per_epic_sync_path.write_text(result.sync_map.model_dump_json(indent=2), encoding="utf-8")

            merged_map = merge_sync_maps(per_epic_maps)
            Path(self._config.sync_path).write_text(merged_map.model_dump_json(indent=2), encoding="utf-8")

            return SyncResult(
                sync_map=merged_map,
                epics_created=epics_created,
                stories_created=stories_created,
                tasks_created=tasks_created,
                dry_run=self._config.dry_run,
            )
