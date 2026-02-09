"""Abstract base class for issue-tracking / project-management providers.

Every concrete provider (GitHub, Jira, Linear, …) must implement this
interface so the :class:`~planpilot.sync.engine.SyncEngine` can orchestrate
syncs without knowing *which* system it talks to.

All methods are ``async``; providers that wrap a synchronous transport
(e.g. the ``gh`` CLI) should use ``asyncio.create_subprocess_exec`` or
``asyncio.to_thread``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from planpilot.models.item import CreateItemInput, ItemFields, UpdateItemInput

if TYPE_CHECKING:
    from planpilot.models.item import Item


class Provider(ABC):
    """Abstract provider for issue tracking and project management systems.

    Used as an async context manager. Construction, auth, and setup happen
    in __aenter__. Cleanup happens in __aexit__. All CRUD operations (create,
    read, update, delete) return rich Item objects (Active Record pattern).
    """

    # ---- Context manager lifecycle ----

    @abstractmethod
    async def __aenter__(self) -> Provider:
        """Enter async context manager.

        Called when entering ``async with Provider(...) as provider:``.
        Perform authentication, target resolution, setup, etc. here.

        Returns:
            self
        """

    @abstractmethod
    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit async context manager.

        Called when exiting the ``async with`` block. Clean up connections, etc.

        Args:
            exc_type: Exception type if one was raised in the block, else None
            exc_val: Exception value if one was raised in the block, else None
            exc_tb: Exception traceback if one was raised in the block, else None
        """

    # ---- Search ----

    @abstractmethod
    async def search_items(self, filters: ItemFields) -> list[Item]:
        """Search for work items matching the given filters.

        Generic search accepting platform-agnostic ItemFields. Providers map
        these fields internally. Unsupported filter fields are ignored.

        Args:
            filters: Search filters (labels, status, etc.)

        Returns:
            List of matching Item instances.
        """

    # ---- CRUD (all return Item) ----

    @abstractmethod
    async def create_item(self, input: CreateItemInput) -> Item:
        """Create a new work item.

        Atomically handles:
        - Issue/card creation
        - Type assignment (if applicable)
        - Field settings (status, priority, size, iteration, etc.)
        - Adding to project board (if applicable)

        Args:
            input: All data required to create the item.

        Returns:
            Newly-created Item with all data populated.

        Raises:
            ProviderError: If creation fails.
        """

    @abstractmethod
    async def update_item(self, item_id: str, input: UpdateItemInput) -> Item:
        """Update an existing work item.

        Only non-None fields in input are applied.

        Args:
            item_id: Opaque provider ID of the item to update.
            input: Fields to update.

        Returns:
            Updated Item.

        Raises:
            ProviderError: If update fails.
        """

    @abstractmethod
    async def get_item(self, item_id: str) -> Item:
        """Fetch a single work item by its provider ID.

        Args:
            item_id: Opaque provider ID.

        Returns:
            The Item.

        Raises:
            ProviderError: If the item is not found or fetch fails.
        """

    @abstractmethod
    async def delete_item(self, item_id: str) -> None:
        """Delete a work item.

        Args:
            item_id: Opaque provider ID.

        Raises:
            ProviderError: If deletion fails.
        """
