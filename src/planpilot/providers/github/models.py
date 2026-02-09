"""GitHub-specific provider models.

These models are used internally by the GitHub provider and are not
part of the provider-agnostic abstraction.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from planpilot.models.project import FieldValue, ResolvedField


# ------------------------------------------------------------------
# Resolved project context (GitHub-specific)
# ------------------------------------------------------------------


class ProjectContext(BaseModel):
    """Resolved GitHub project board context returned by provider."""

    project_id: str
    status_field: ResolvedField | None = None
    priority_field: ResolvedField | None = None
    iteration_field: ResolvedField | None = None
    size_field_id: str | None = None
    size_options: list[dict[str, str]] = Field(default_factory=list)
    item_map: dict[str, str] = Field(default_factory=dict)
    """Mapping of content (issue) node-ID → project-item ID."""


# ------------------------------------------------------------------
# Repository context (GitHub-specific)
# ------------------------------------------------------------------


IssueTypeMap = dict[str, str]
"""Mapping of issue-type name (e.g. ``"Epic"``) to its node ID."""


class RepoContext(BaseModel):
    """Resolved GitHub repository context returned by provider."""

    repo_id: str | None = None
    label_id: str | None = None
    issue_type_ids: IssueTypeMap = Field(default_factory=dict)
