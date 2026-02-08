"""Models for sync results and the sync map persisted to disk."""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, Field


class SyncEntry(BaseModel):
    """Sync-map entry for a single issue (epic, story, or task)."""

    issue_number: int
    url: str
    node_id: str
    project_item_id: str | None = None


class SyncMap(BaseModel):
    """The full sync map written to disk after a sync run.

    Maps plan entity IDs to their corresponding GitHub issue metadata.
    """

    plan_id: str
    repo: str
    project_url: str
    epics: dict[str, SyncEntry] = Field(default_factory=dict)
    stories: dict[str, SyncEntry] = Field(default_factory=dict)
    tasks: dict[str, SyncEntry] = Field(default_factory=dict)


class SyncResult(BaseModel):
    """Value returned by :meth:`SyncEngine.sync`."""

    sync_map: SyncMap
    epics_created: int = 0
    stories_created: int = 0
    tasks_created: int = 0
    dry_run: bool = False


def merge_sync_maps(sync_maps: list[SyncMap]) -> SyncMap:
    """Merge per-epic sync maps into one combined map.

    Raises:
        ValueError: If input is empty, contains incompatible metadata, or has duplicate entity IDs.
    """
    if not sync_maps:
        raise ValueError("cannot merge empty sync map list")

    repo = sync_maps[0].repo
    project_url = sync_maps[0].project_url
    plan_ids = sorted(sync_map.plan_id for sync_map in sync_maps)
    combined_hash = hashlib.sha1("|".join(plan_ids).encode("utf-8")).hexdigest()[:12]

    merged = SyncMap(
        plan_id=f"combined-{combined_hash}",
        repo=repo,
        project_url=project_url,
    )

    for sync_map in sync_maps:
        if sync_map.repo != repo:
            raise ValueError(f"incompatible repo in sync map: {sync_map.repo!r} != {repo!r}")
        if sync_map.project_url != project_url:
            raise ValueError(
                f"incompatible project_url in sync map: {sync_map.project_url!r} != {project_url!r}"
            )

        for entity_type, source, destination in (
            ("epic", sync_map.epics, merged.epics),
            ("story", sync_map.stories, merged.stories),
            ("task", sync_map.tasks, merged.tasks),
        ):
            for entity_id, entry in source.items():
                if entity_id in destination:
                    raise ValueError(f"duplicate {entity_type} id while merging sync maps: {entity_id}")
                destination[entity_id] = entry.model_copy(deep=True)

    return merged
