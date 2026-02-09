"""Configuration contracts."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class FieldConfig(BaseModel):
    status: str = "Backlog"
    priority: str = "P1"
    iteration: str = "active"
    size_field: str = "Size"
    size_from_tshirt: bool = True
    create_type_strategy: str = "issue-type"
    create_type_map: dict[str, str] = Field(default_factory=lambda: {"EPIC": "Epic", "STORY": "Story", "TASK": "Task"})


class PlanPaths(BaseModel):
    epics: Path | None = None
    stories: Path | None = None
    tasks: Path | None = None
    unified: Path | None = None

    @model_validator(mode="after")
    def validate_path_mode(self) -> PlanPaths:
        has_split = any(path is not None for path in (self.epics, self.stories, self.tasks))
        has_unified = self.unified is not None
        if not has_split and not has_unified:
            raise ValueError("At least one of unified/epics/stories/tasks must be set")
        if has_unified and has_split:
            raise ValueError("unified cannot be combined with epics/stories/tasks")
        return self


class PlanPilotConfig(BaseModel):
    provider: str
    target: str
    auth: str = "gh-cli"
    token: str | None = None
    board_url: str
    plan_paths: PlanPaths
    validation_mode: str = "strict"
    sync_path: Path = Path("sync-map.json")
    label: str = "planpilot"
    max_concurrent: int = Field(default=1, ge=1, le=10)
    field_config: FieldConfig = Field(default_factory=FieldConfig)

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def validate_auth_token(self) -> PlanPilotConfig:
        token = (self.token or "").strip()
        if self.auth == "token":
            if not token:
                raise ValueError("token auth requires a non-empty token")
            return self
        if token:
            raise ValueError("token must be unset when auth is not 'token'")
        if self.auth not in {"gh-cli", "env", "token"}:
            raise ValueError("auth must be one of: gh-cli, env, token")
        return self
