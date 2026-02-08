from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class SyncConfig:
    repo: str
    project_url: str
    epics_path: str
    stories_path: str
    tasks_path: str
    sync_path: str
    label: str
    status: str
    priority: str
    iteration: str
    size_field: str
    size_from_tshirt: bool
    apply: bool = False
    dry_run: bool = False
    verbose: bool = False


@dataclass
class IssueRef:
    id: str
    number: int
    url: str


@dataclass
class ProjectFieldIds:
    status_field_id: Optional[str]
    status_option_id: Optional[str]
    priority_field_id: Optional[str]
    priority_option_id: Optional[str]
    iteration_field_id: Optional[str]
    iteration_option_id: Optional[str]
    size_field_id: Optional[str]
    size_options: List[Dict[str, str]]
