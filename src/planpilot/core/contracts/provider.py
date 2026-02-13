"""Provider adapter contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType

from planpilot.core.contracts.item import CreateItemInput, Item, ItemSearchFilters, UpdateItemInput


class Provider(ABC):
    @abstractmethod
    async def __aenter__(self) -> Provider: ...  # pragma: no cover

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...  # pragma: no cover

    @abstractmethod
    async def search_items(self, filters: ItemSearchFilters) -> list[Item]: ...  # pragma: no cover

    @abstractmethod
    async def create_item(self, input: CreateItemInput) -> Item: ...  # pragma: no cover

    @abstractmethod
    async def update_item(self, item_id: str, input: UpdateItemInput) -> Item: ...  # pragma: no cover

    @abstractmethod
    async def get_item(self, item_id: str) -> Item: ...  # pragma: no cover

    @abstractmethod
    async def delete_item(self, item_id: str) -> None: ...  # pragma: no cover
