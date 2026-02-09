"""Provider adapter contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType

from planpilot_v2.contracts.item import CreateItemInput, Item, ItemSearchFilters, UpdateItemInput


class Provider(ABC):
    @abstractmethod
    async def __aenter__(self) -> Provider: ...

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...

    @abstractmethod
    async def search_items(self, filters: ItemSearchFilters) -> list[Item]: ...

    @abstractmethod
    async def create_item(self, input: CreateItemInput) -> Item: ...

    @abstractmethod
    async def update_item(self, item_id: str, input: UpdateItemInput) -> Item: ...

    @abstractmethod
    async def get_item(self, item_id: str) -> Item: ...

    @abstractmethod
    async def delete_item(self, item_id: str) -> None: ...
