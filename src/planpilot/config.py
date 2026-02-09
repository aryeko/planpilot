"""Application-level configuration for a sync run.

:class:`SyncConfig` is built from CLI arguments and carries every setting the
sync engine, provider, and renderer need.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from planpilot.models.project import FieldConfig


class SyncConfig(BaseModel):
    """Top-level configuration for a ``planpilot`` sync run.

    Attributes:
        provider: Provider name (e.g. "github"). Default is "github".
        target: Target designation (e.g. "OWNER/REPO").
        board_url: Full URL to a project/board (optional).
        epics_path: Path to the epics JSON file.
        stories_path: Path to the stories JSON file.
        tasks_path: Path to the tasks JSON file.
        sync_path: Path where the sync map will be written.
        label: Label to apply to all created items.
        field_config: Project field preferences (status, priority, …).
        dry_run: When *True*, no mutations are performed (sync map is still written).
        verbose: When *True*, emit detailed progress to stderr.
    """

    provider: str = "github"
    target: str = Field(alias="repo")
    """Target designation. Accepts legacy 'repo' via alias."""
    board_url: str | None = Field(default=None, alias="project_url")
    """Board URL (optional). Accepts legacy 'project_url' via alias."""
    epics_path: Path
    stories_path: Path
    tasks_path: Path
    sync_path: Path
    label: str = "planpilot"
    field_config: FieldConfig = FieldConfig()
    dry_run: bool = False
    verbose: bool = False

    model_config = {"populate_by_name": True}
