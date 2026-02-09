"""Models for provider-agnostic work items and item operations.

These models form the core abstraction layer for the provider redesign.
They replace GitHub-specific concepts (IssueRef, ExistingIssue) with
universal work-item concepts that any provider can implement.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from planpilot.models.sync import SyncEntry
    from planpilot.providers.base import Provider


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


class Item:
    """A work item with provider-bound operations.

    Returned by Provider CRUD methods. Contains item data and async methods
    for relation management. This is the runtime representation of an item
    (non-serializable) with provider-bound methods.

    Data properties are read-only (reflect server state after the last mutation).
    """

    # ---- Data (read-only, set by provider) ----
    id: str  # opaque provider ID (GH node_id, Jira key, ...)
    key: str  # human-readable ref ("#123", "PROJ-456")
    url: str  # web URL
    title: str
    body: str
    item_type: ItemType | None
    parent_id: str | None
    labels: list[str]

    # ---- Provider back-reference (internal) ----
    _provider: Provider
    _ctx: TargetContext

    def __init__(
        self,
        *,
        id: str,
        key: str,
        url: str,
        title: str,
        body: str = "",
        item_type: ItemType | None = None,
        parent_id: str | None = None,
        labels: list[str] | None = None,
        provider: Provider,
        ctx: TargetContext,
    ) -> None:
        """Initialize an Item with provider context.

        Args:
            id: Opaque provider ID
            key: Human-readable reference
            url: Web URL to the item
            title: Item title
            body: Item body/description
            item_type: Item type (epic/story/task)
            parent_id: Parent item's provider ID (if any)
            labels: Labels/tags on the item
            provider: Back-reference to the provider instance
            ctx: Opaque provider context
        """
        self.id = id
        self.key = key
        self.url = url
        self.title = title
        self.body = body
        self.item_type = item_type
        self.parent_id = parent_id
        self.labels = labels or []
        self._provider = provider
        self._ctx = ctx

    # ---- Relation methods (async, to be overridden by subclasses) ----

    async def set_parent(self, parent: Item) -> None:
        """Set the parent of this item.

        Args:
            parent: The parent Item

        Raises:
            NotImplementedError: If not implemented by provider subclass
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.set_parent() not implemented"
        )

    async def add_child(self, child: Item) -> None:
        """Add a child to this item.

        Args:
            child: The child Item

        Raises:
            NotImplementedError: If not implemented by provider subclass
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.add_child() not implemented"
        )

    async def remove_child(self, child: Item) -> None:
        """Remove a child from this item.

        Args:
            child: The child Item

        Raises:
            NotImplementedError: If not implemented by provider subclass
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.remove_child() not implemented"
        )

    async def get_children(self) -> list[Item]:
        """Get all children of this item.

        Returns:
            List of child Items

        Raises:
            NotImplementedError: If not implemented by provider subclass
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.get_children() not implemented"
        )

    async def add_dependency(self, blocker: Item) -> None:
        """Add a blocking dependency to this item.

        Args:
            blocker: The Item that blocks this one

        Raises:
            NotImplementedError: If not implemented by provider subclass
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.add_dependency() not implemented"
        )

    async def remove_dependency(self, blocker: Item) -> None:
        """Remove a blocking dependency from this item.

        Args:
            blocker: The Item that was blocking this one

        Raises:
            NotImplementedError: If not implemented by provider subclass
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.remove_dependency() not implemented"
        )

    async def get_dependencies(self) -> list[Item]:
        """Get all items that block this one.

        Returns:
            List of blocking Items

        Raises:
            NotImplementedError: If not implemented by provider subclass
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.get_dependencies() not implemented"
        )

    # ---- Serialization ----

    def to_sync_entry(self) -> SyncEntry:
        """Extract serializable SyncEntry for persistence.

        Returns:
            SyncEntry with id, key, and url
        """
        from planpilot.models.sync import SyncEntry
        return SyncEntry(id=self.id, key=self.key, url=self.url)
