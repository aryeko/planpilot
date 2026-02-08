"""Models for provider-side project and repository context.

These models carry resolved IDs and metadata fetched from the provider
(GitHub, Jira, Linear, etc.) so the sync engine can work with them in a
provider-agnostic way.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ------------------------------------------------------------------
# Field configuration (what the user *wants* to set)
# ------------------------------------------------------------------


class FieldConfig(BaseModel):
    """User-specified project field preferences."""

    status: str = "Backlog"
    priority: str = "P1"
    iteration: str = "active"
    size_field: str = "Size"
    size_from_tshirt: bool = True


class FieldValue(BaseModel):
    """A single project-field value to set on an item.

    Exactly one of the value fields should be populated.
    """

    single_select_option_id: str | None = None
    iteration_id: str | None = None
    text: str | None = None
    number: float | None = None


# ------------------------------------------------------------------
# Resolved project context (what the provider *found*)
# ------------------------------------------------------------------


class ResolvedField(BaseModel):
    """A project field whose ID and target option have been resolved."""

    field_id: str
    value: FieldValue


class ProjectContext(BaseModel):
    """Resolved project board context returned by a provider."""

    project_id: str
    status_field: ResolvedField | None = None
    priority_field: ResolvedField | None = None
    iteration_field: ResolvedField | None = None
    size_field_id: str | None = None
    size_options: list[dict[str, str]] = Field(default_factory=list)
    item_map: dict[str, str] = Field(default_factory=dict)
    """Mapping of content (issue) node-ID → project-item ID."""


# ------------------------------------------------------------------
# Repository context
# ------------------------------------------------------------------

IssueTypeMap = dict[str, str]
"""Mapping of issue-type name (e.g. ``"Epic"``) to its node ID."""


class RepoContext(BaseModel):
    """Resolved repository context returned by a provider."""

    repo_id: str | None = None
    label_id: str | None = None
    issue_type_ids: IssueTypeMap = Field(default_factory=dict)


# ------------------------------------------------------------------
# Issue-level models shared across providers
# ------------------------------------------------------------------


class IssueRef(BaseModel):
    """Lightweight reference to a created/existing issue."""

    id: str
    number: int
    url: str


class ExistingIssue(BaseModel):
    """An issue returned by the provider's search/query endpoint."""

    id: str
    number: int
    body: str = ""


class CreateIssueInput(BaseModel):
    """Data needed to create a new issue via a provider."""

    repo_id: str
    title: str
    body: str
    label_ids: list[str] = Field(default_factory=list)


# ------------------------------------------------------------------
# Relation maps
# ------------------------------------------------------------------


class RelationMap(BaseModel):
    """Parent and blocked-by relationships for a set of issues."""

    parents: dict[str, str | None] = Field(default_factory=dict)
    """issue-node-ID → parent-node-ID (or None)."""

    blocked_by: dict[str, set[str]] = Field(default_factory=dict)
    """issue-node-ID → set of blocking issue-node-IDs."""
