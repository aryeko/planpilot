"""In-memory dry-run provider."""

from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType

from planpilot_v2.contracts.exceptions import ProviderError
from planpilot_v2.contracts.item import CreateItemInput, Item, ItemSearchFilters, UpdateItemInput
from planpilot_v2.contracts.plan import PlanItemType
from planpilot_v2.contracts.provider import Provider


@dataclass
class DryRunItem(Item):
    """Placeholder item returned by DryRunProvider."""

    _id: str
    _title: str
    _body: str
    _item_type: PlanItemType | None

    def __init__(self, *, id: str, title: str, body: str, item_type: PlanItemType | None) -> None:
        self._id = id
        self._title = title
        self._body = body
        self._item_type = item_type

    @property
    def id(self) -> str:
        return self._id

    @property
    def key(self) -> str:
        return "dry-run"

    @property
    def url(self) -> str:
        return "dry-run"

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
        return None

    async def add_dependency(self, blocker: Item) -> None:
        return None


class DryRunProvider(Provider):
    """Provider that returns deterministic placeholders without network calls."""

    def __init__(self) -> None:
        self._counter = 0
        self._items: dict[str, DryRunItem] = {}

    async def __aenter__(self) -> DryRunProvider:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        return None

    async def search_items(self, filters: ItemSearchFilters) -> list[Item]:
        return []

    async def create_item(self, input: CreateItemInput) -> Item:
        self._counter += 1
        item = DryRunItem(id=f"dry-run-{self._counter}", title=input.title, body=input.body, item_type=input.item_type)
        self._items[item.id] = item
        return item

    async def update_item(self, item_id: str, input: UpdateItemInput) -> Item:
        item = self._items.get(item_id)
        if item is None:
            raise ProviderError(f"Item not found: {item_id}")
        title = input.title if input.title is not None else item.title
        body = input.body if input.body is not None else item.body
        item_type = input.item_type if input.item_type is not None else item.item_type
        updated = DryRunItem(id=item.id, title=title, body=body, item_type=item_type)
        self._items[item.id] = updated
        return updated

    async def get_item(self, item_id: str) -> Item:
        item = self._items.get(item_id)
        if item is None:
            raise ProviderError(f"Item not found: {item_id}")
        return item

    async def delete_item(self, item_id: str) -> None:
        self._items.pop(item_id, None)
