"""GitHub item implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from planpilot_v2.contracts.exceptions import ProviderCapabilityError
from planpilot_v2.contracts.item import Item
from planpilot_v2.contracts.plan import PlanItemType

if TYPE_CHECKING:
    from planpilot_v2.providers.github.provider import GitHubProvider


class GitHubItem(Item):
    def __init__(
        self,
        *,
        provider: GitHubProvider,
        issue_id: str,
        number: int,
        title: str,
        body: str,
        item_type: PlanItemType | None,
        url: str,
    ) -> None:
        self.provider = provider
        self.issue_id = issue_id
        self.number = number
        self._title = title
        self._body = body
        self._item_type = item_type
        self._url = url

    @property
    def id(self) -> str:
        return self.issue_id

    @property
    def key(self) -> str:
        return f"#{self.number}"

    @property
    def url(self) -> str:
        return self._url

    @property
    def title(self) -> str:
        return self._title

    @property
    def body(self) -> str:
        return self._body

    @property
    def item_type(self) -> PlanItemType | None:
        return self._item_type

    async def set_parent(self, parent: Item) -> None:
        if not self.provider.context.supports_sub_issues:
            raise ProviderCapabilityError("GitHub provider does not support sub-issues.", capability="sub-issues")
        await self.provider.add_sub_issue(child_issue_id=self.id, parent_issue_id=parent.id)

    async def add_dependency(self, blocker: Item) -> None:
        if not self.provider.context.supports_blocked_by:
            raise ProviderCapabilityError("GitHub provider does not support blocked-by.", capability="blocked-by")
        await self.provider.add_blocked_by(blocked_issue_id=self.id, blocker_issue_id=blocker.id)
