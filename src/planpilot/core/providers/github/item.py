"""GitHub item implementation."""

from __future__ import annotations

from typing import Any

from planpilot.core.contracts.exceptions import ProviderCapabilityError
from planpilot.core.contracts.item import Item
from planpilot.core.contracts.plan import PlanItemType


class GitHubItem(Item):
    def __init__(
        self,
        *,
        provider: Any,
        issue_id: str,
        number: int,
        title: str,
        body: str,
        item_type: PlanItemType | None,
        url: str,
        labels: list[str] | None = None,
        size: str | None = None,
    ) -> None:
        self.provider = provider
        self.issue_id = issue_id
        self.number = number
        self._title = title
        self._body = body
        self._item_type = item_type
        self._url = url
        self._labels = labels or []
        self._size = size

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

    @property
    def labels(self) -> list[str]:
        return list(self._labels)

    @property
    def size(self) -> str | None:
        return self._size

    async def set_parent(self, parent: Item) -> None:
        if not self.provider.context.supports_sub_issues:
            raise ProviderCapabilityError("GitHub provider does not support sub-issues.", capability="sub-issues")
        await self.provider.add_sub_issue(child_issue_id=self.id, parent_issue_id=parent.id)

    async def add_dependency(self, blocker: Item) -> None:
        if not self.provider.context.supports_blocked_by:
            raise ProviderCapabilityError("GitHub provider does not support blocked-by.", capability="blocked-by")
        await self.provider.add_blocked_by(blocked_issue_id=self.id, blocker_issue_id=blocker.id)

    async def reconcile_relations(self, *, parent: Item | None, blockers: list[Item]) -> None:
        desired_parent_id = parent.id if parent is not None else None
        desired_blocker_ids = {blocker.id for blocker in blockers}

        if desired_parent_id is not None and not self.provider.context.supports_sub_issues:
            raise ProviderCapabilityError("GitHub provider does not support sub-issues.", capability="sub-issues")
        if desired_blocker_ids and not self.provider.context.supports_blocked_by:
            raise ProviderCapabilityError("GitHub provider does not support blocked-by.", capability="blocked-by")

        current_parent_id, current_blocker_ids = await self.provider.get_relations(issue_id=self.id)

        if self.provider.context.supports_sub_issues:
            if current_parent_id is not None and current_parent_id != desired_parent_id:
                await self.provider.remove_sub_issue(child_issue_id=self.id, parent_issue_id=current_parent_id)
            if desired_parent_id is not None and desired_parent_id != current_parent_id:
                await self.provider.add_sub_issue(child_issue_id=self.id, parent_issue_id=desired_parent_id)

        if self.provider.context.supports_blocked_by:
            stale_blocker_ids = current_blocker_ids.difference(desired_blocker_ids)
            missing_blocker_ids = desired_blocker_ids.difference(current_blocker_ids)
            for blocker_id in sorted(stale_blocker_ids):
                await self.provider.remove_blocked_by(blocked_issue_id=self.id, blocker_issue_id=blocker_id)
            for blocker_id in sorted(missing_blocker_ids):
                await self.provider.add_blocked_by(blocked_issue_id=self.id, blocker_issue_id=blocker_id)
