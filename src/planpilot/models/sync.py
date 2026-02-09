"""Models for sync results and the sync map persisted to disk."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SyncEntry(BaseModel):
    """Sync-map entry for a single work item (epic, story, or task).

    Provider-agnostic representation carrying:
    - id: opaque provider ID (was node_id)
    - key: human-readable reference (was issue_number)
    - url: web URL
    """

    id: str = Field(alias="node_id")
    """Opaque provider ID. Accepts legacy 'node_id' via alias."""
    key: str = Field(alias="issue_number")
    """Human-readable reference. Accepts legacy 'issue_number' via alias."""
    url: str

    model_config = {"populate_by_name": True}


class SyncMap(BaseModel):
    """The full sync map written to disk after a sync run.

    Provider-agnostic mapping of plan entity IDs to their corresponding work item metadata.
    """

    plan_id: str
    target: str = Field(alias="repo")
    """Target designation (e.g. 'owner/repo'). Accepts legacy 'repo' via alias."""
    board_url: str | None = Field(default=None, alias="project_url")
    """Board URL (optional). Accepts legacy 'project_url' via alias."""
    epics: dict[str, SyncEntry] = Field(default_factory=dict)
    stories: dict[str, SyncEntry] = Field(default_factory=dict)
    tasks: dict[str, SyncEntry] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class SyncResult(BaseModel):
    """Value returned by :meth:`SyncEngine.sync`."""

    sync_map: SyncMap
    epics_created: int = 0
    stories_created: int = 0
    tasks_created: int = 0
    dry_run: bool = False
