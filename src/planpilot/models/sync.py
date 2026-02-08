"""Models for sync results and the sync map persisted to disk."""

from __future__ import annotations

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
