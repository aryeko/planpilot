"""Application-level configuration for a sync run.

:class:`SyncConfig` is built from CLI arguments and carries every setting the
sync engine, provider, and renderer need.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from planpilot.models.project import FieldConfig


class SyncConfig(BaseModel):
    """Top-level configuration for a ``planpilot`` sync run.

    Attributes:
        repo: GitHub repository in ``OWNER/REPO`` format.
        project_url: Full URL to a GitHub Projects v2 board.
        epics_path: Path to the epics JSON file.
        stories_path: Path to the stories JSON file.
        tasks_path: Path to the tasks JSON file.
        sync_path: Path where the sync map will be written.
        label: Label to apply to all created issues.
        field_config: Project field preferences (status, priority, …).
        dry_run: When *True*, no write operations are performed.
        verbose: When *True*, emit detailed progress to stderr.
    """

    repo: str
    project_url: str
    epics_path: Path
    stories_path: Path
    tasks_path: Path
    sync_path: Path
    label: str = "planpilot"
    field_config: FieldConfig = FieldConfig()
    dry_run: bool = False
    verbose: bool = False
