"""Models for provider-agnostic work items and item operations.

These models form the core abstraction layer for the provider redesign.
They replace GitHub-specific concepts (IssueRef, ExistingIssue) with
universal work-item concepts that any provider can implement.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ItemType(StrEnum):
    """Universal work-item type discriminator."""

    EPIC = "epic"
    STORY = "story"
    TASK = "task"


class ItemFields(BaseModel):
    """Generic work-item fields accepted by create/update operations.

    Providers map these to their platform-specific representations.
    Unsupported fields are silently ignored.

    All fields are optional. None means "don't set / don't change".
    This allows the same model to work for both create (most fields populated)
    and update (only changed fields populated).
    """

    title: str | None = None
    body: str | None = None
    item_type: ItemType | None = None
    parent_id: str | None = None
    labels: list[str] | None = None
    status: str | None = None  # "Backlog", "In Progress", "Done"
    priority: str | None = None  # "P0".."P3" or "Critical"/"High"/...
    size: str | None = None  # t-shirt: "XS", "S", "M", "L", "XL"
    iteration: str | None = None  # sprint/cycle name or "active"
    assignees: list[str] | None = None
    milestone: str | None = None
    due_date: str | None = None  # ISO 8601 date


class CreateItemInput(ItemFields):
    """Fields for creating a new work item.

    title and item_type are required (overridden from ItemFields).
    """

    title: str
    item_type: ItemType
    body: str = ""


class UpdateItemInput(ItemFields):
    """Fields for updating an existing work item.

    All fields are optional; inherited from ItemFields.
    Only non-None fields are applied.
    """

    pass


class TargetContext(BaseModel):
    """Opaque context returned by Provider.__aenter__().

    Providers subclass this to store resolved IDs, field mappings,
    and other provider-specific state. The engine passes it through
    without inspecting it.
    """

    pass


class ExistingItemMap(BaseModel):
    """Categorized existing items found during discovery."""

    epics: dict[str, str] = Field(default_factory=dict)
    """plan_id -> provider Item ID mapping."""
    stories: dict[str, str] = Field(default_factory=dict)
    """plan_id -> provider Item ID mapping."""
    tasks: dict[str, str] = Field(default_factory=dict)
    """plan_id -> provider Item ID mapping."""
