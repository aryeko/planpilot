"""In-memory provider fake for v2 tests."""

from __future__ import annotations

from dataclasses import dataclass

from planpilot.core.contracts.exceptions import ProviderError
from planpilot.core.contracts.item import CreateItemInput, Item, ItemSearchFilters, UpdateItemInput
from planpilot.core.contracts.plan import PlanItemType
from planpilot.core.contracts.provider import Provider


@dataclass
class FakeItem(Item):
    _id: str
    _key: str
    _url: str
    _title: str
    _body: str
    _item_type: PlanItemType | None
    _provider: FakeProvider
    _labels: list[str]
    _size: str | None = None

    @property
    def id(self) -> str:
        return self._id

    @property
    def key(self) -> str:
        return self._key

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
        self._provider.parents[self.id] = parent.id

    async def add_dependency(self, blocker: Item) -> None:
        deps = self._provider.dependencies.setdefault(self.id, set())
        deps.add(blocker.id)

    async def reconcile_relations(self, *, parent: Item | None, blockers: list[Item]) -> None:
        if parent is None:
            self._provider.parents.pop(self.id, None)
        else:
            self._provider.parents[self.id] = parent.id
        blocker_ids = {blocker.id for blocker in blockers}
        if blocker_ids:
            self._provider.dependencies[self.id] = blocker_ids
        else:
            self._provider.dependencies.pop(self.id, None)


class FakeProvider(Provider):
    """In-memory provider with deterministic IDs/keys and spy tracking."""

    def __init__(self) -> None:
        self.items: dict[str, FakeItem] = {}
        self.parents: dict[str, str] = {}
        self.dependencies: dict[str, set[str]] = {}
        self._next_number = 1

        self.search_calls: list[ItemSearchFilters] = []
        self.create_calls: list[CreateItemInput] = []
        self.update_calls: list[tuple[str, UpdateItemInput]] = []
        self.delete_calls: list[str] = []

    async def __aenter__(self) -> FakeProvider:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[override]
        return None

    async def search_items(self, filters: ItemSearchFilters) -> list[Item]:
        self.search_calls.append(filters)
        matched: list[Item] = []
        for item in self.items.values():
            label_match = all(label in getattr(item, "_labels", []) for label in filters.labels)
            body_match = filters.body_contains in item.body
            if label_match and body_match:
                matched.append(item)
        return matched

    async def create_item(self, input: CreateItemInput) -> Item:
        self.create_calls.append(input)
        n = self._next_number
        self._next_number += 1
        item = FakeItem(
            _id=f"fake-id-{n}",
            _key=f"#{n}",
            _url=f"https://fake/issues/{n}",
            _title=input.title,
            _body=input.body,
            _item_type=input.item_type,
            _provider=self,
            _labels=list(input.labels),
            _size=input.size,
        )
        self.items[item.id] = item
        return item

    async def update_item(self, item_id: str, input: UpdateItemInput) -> Item:
        self.update_calls.append((item_id, input))
        item = self.items.get(item_id)
        if item is None:
            raise ProviderError(f"Item not found: {item_id}")
        if input.title is not None:
            item._title = input.title
        if input.body is not None:
            item._body = input.body
        if input.item_type is not None:
            item._item_type = input.item_type
        if input.labels is not None:
            item._labels = list(input.labels)
        if input.size is not None:
            item._size = input.size
        return item

    async def get_item(self, item_id: str) -> Item:
        item = self.items.get(item_id)
        if item is None:
            raise ProviderError(f"Item not found: {item_id}")
        return item

    async def delete_item(self, item_id: str) -> None:
        self.delete_calls.append(item_id)
        if item_id not in self.items:
            raise ProviderError(f"Item not found: {item_id}")
        del self.items[item_id]
        self.parents.pop(item_id, None)
        self.dependencies.pop(item_id, None)

    def set_item_identity(self, item_id: str, *, key: str | None = None, url: str | None = None) -> None:
        item = self.items.get(item_id)
        if item is None:
            raise ProviderError(f"Item not found: {item_id}")
        if key is not None:
            item._key = key
        if url is not None:
            item._url = url
