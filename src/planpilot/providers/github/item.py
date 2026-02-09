"""GitHub Item implementation with provider-bound relation methods."""

from __future__ import annotations

from typing import TYPE_CHECKING

from planpilot.models.item import ItemType
from planpilot.models.item import Item

if TYPE_CHECKING:
    from planpilot.models.item import TargetContext
    from planpilot.providers.github.provider import GitHubProvider


class GitHubItem(Item):
    """GitHub-specific Item with GraphQL-backed relation methods."""

    _provider: GitHubProvider  # Type hint override
    _ctx: TargetContext

    async def set_parent(self, parent: GitHubItem) -> None:
        """Set the parent of this item via GitHub's sub-issue API.

        Args:
            parent: The parent GitHubItem
        """
        # Implementation will call GitHub GraphQL API
        # For now, defer to provider
        await self._provider._set_item_parent(self, parent)

    async def add_child(self, child: GitHubItem) -> None:
        """Add a child to this item via GitHub's sub-issue API.

        Args:
            child: The child GitHubItem
        """
        # Implementation will call GitHub GraphQL API
        await self._provider._add_item_child(self, child)

    async def remove_child(self, child: GitHubItem) -> None:
        """Remove a child from this item via GitHub's sub-issue API.

        Args:
            child: The child GitHubItem
        """
        # Implementation will call GitHub GraphQL API
        await self._provider._remove_item_child(self, child)

    async def get_children(self) -> list[GitHubItem]:
        """Get all children of this item from GitHub.

        Returns:
            List of child GitHubItems
        """
        # Implementation will call GitHub GraphQL API
        return await self._provider._get_item_children(self)

    async def add_dependency(self, blocker: GitHubItem) -> None:
        """Add a blocking dependency to this item via GitHub's issue relations.

        Args:
            blocker: The Item that blocks this one
        """
        # Implementation will call GitHub GraphQL API
        await self._provider._add_item_dependency(self, blocker)

    async def remove_dependency(self, blocker: GitHubItem) -> None:
        """Remove a blocking dependency from this item via GitHub's issue relations.

        Args:
            blocker: The Item that was blocking this one
        """
        # Implementation will call GitHub GraphQL API
        await self._provider._remove_item_dependency(self, blocker)

    async def get_dependencies(self) -> list[GitHubItem]:
        """Get all items that block this one from GitHub.

        Returns:
            List of blocking GitHubItems
        """
        # Implementation will call GitHub GraphQL API
        return await self._provider._get_item_dependencies(self)
