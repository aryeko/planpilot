"""Active Record pattern: Item class carrying provider-bound operations.

Item instances are returned by Provider CRUD methods. Each Item holds a
back-reference to its provider and context, enabling bound methods for
relation management and other operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from planpilot.models.item import ItemType
from planpilot.models.sync import SyncEntry

if TYPE_CHECKING:
    from planpilot.models.item import TargetContext
    from planpilot.providers.base import Provider


class Item:
    """A work item with provider-bound operations.

    Returned by Provider CRUD methods. Contains item data and async methods
    for relation management.

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
        return SyncEntry(id=self.id, key=self.key, url=self.url)
