from dataclasses import dataclass


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
    status_field_id: str | None
    status_option_id: str | None
    priority_field_id: str | None
    priority_option_id: str | None
    iteration_field_id: str | None
    iteration_option_id: str | None
    size_field_id: str | None
    size_options: list[dict[str, str]]
