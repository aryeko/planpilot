"""In-memory dry-run provider."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType

from planpilot.core.contracts.exceptions import ProviderError
from planpilot.core.contracts.item import CreateItemInput, Item, ItemSearchFilters, UpdateItemInput
from planpilot.core.contracts.plan import PlanItemType
from planpilot.core.contracts.provider import Provider


@dataclass(frozen=True)
class DryRunOperation:
    """Deterministic dry-run operation log entry."""

    sequence: int
    name: str
    item_id: str | None
    payload: dict[str, str]


@dataclass
class DryRunItem(Item):
    """Placeholder item returned by DryRunProvider."""

    _id: str
    _title: str
    _body: str
    _item_type: PlanItemType | None
    _labels: tuple[str, ...]
    _record_operation: Callable[[str, str | None, dict[str, str]], None] | None

    def __init__(
        self,
        *,
        id: str,
        title: str,
        body: str,
        item_type: PlanItemType | None,
        labels: list[str] | tuple[str, ...] | None = None,
        record_operation: Callable[[str, str | None, dict[str, str]], None] | None = None,
    ) -> None:
        self._id = id
        self._title = title
        self._body = body
        self._item_type = item_type
        self._labels = tuple(labels or ())
        self._record_operation = record_operation

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
        if self._record_operation is not None:
            self._record_operation("set_parent", self.id, {"parent_id": parent.id})

    async def add_dependency(self, blocker: Item) -> None:
        if self._record_operation is not None:
            self._record_operation("add_dependency", self.id, {"blocker_id": blocker.id})

    async def reconcile_relations(self, *, parent: Item | None, blockers: list[Item]) -> None:
        if self._record_operation is not None:
            payload = {
                "parent_id": parent.id if parent is not None else "",
                "blocker_ids": ",".join(sorted(blocker.id for blocker in blockers)),
            }
            self._record_operation("reconcile_relations", self.id, payload)


class DryRunProvider(Provider):
    """Provider that returns deterministic placeholders without network calls."""

    def __init__(self) -> None:
        self._counter = 0
        self._items: dict[str, DryRunItem] = {}
        self._operation_counter = 0
        self._operations: list[DryRunOperation] = []

    @property
    def operations(self) -> tuple[DryRunOperation, ...]:
        return tuple(self._operations)

    def _record_operation(self, name: str, item_id: str | None, payload: dict[str, str] | None = None) -> None:
        self._operation_counter += 1
        self._operations.append(
            DryRunOperation(
                sequence=self._operation_counter,
                name=name,
                item_id=item_id,
                payload=payload or {},
            )
        )

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
        labels = getattr(filters, "labels", [])
        body_contains = getattr(filters, "body_contains", "")
        self._record_operation(
            "search_items",
            None,
            {
                "labels": ",".join(str(label) for label in labels),
                "body_contains": str(body_contains),
            },
        )
        body_contains_text = str(body_contains)
        label_set = {str(label) for label in labels}
        matched: list[Item] = []
        for item in self._items.values():
            if body_contains_text and body_contains_text not in item.body:
                continue
            if label_set and not label_set.issubset(set(item._labels)):
                continue
            matched.append(item)
        return matched

    async def create_item(self, input: CreateItemInput) -> Item:
        self._counter += 1
        item_id = f"dry-run-{self._counter}"
        self._record_operation(
            "create_item",
            item_id,
            {
                "title": input.title,
                "item_type": input.item_type.value,
            },
        )
        item = DryRunItem(
            id=item_id,
            title=input.title,
            body=input.body,
            item_type=input.item_type,
            labels=input.labels,
            record_operation=self._record_operation,
        )
        self._items[item.id] = item
        return item

    async def update_item(self, item_id: str, input: UpdateItemInput) -> Item:
        payload: dict[str, str] = {}
        if input.title is not None:
            payload["title"] = input.title
        if input.body is not None:
            payload["body"] = input.body
        if input.item_type is not None:
            payload["item_type"] = input.item_type.value
        self._record_operation("update_item", item_id, payload)

        item = self._items.get(item_id)
        if item is None:
            raise ProviderError(f"Item not found: {item_id}")
        title = input.title if input.title is not None else item.title
        body = input.body if input.body is not None else item.body
        item_type = input.item_type if input.item_type is not None else item.item_type
        labels = input.labels if input.labels is not None else list(item._labels)
        updated = DryRunItem(
            id=item.id,
            title=title,
            body=body,
            item_type=item_type,
            labels=labels,
            record_operation=self._record_operation,
        )
        self._items[item.id] = updated
        return updated

    async def get_item(self, item_id: str) -> Item:
        self._record_operation("get_item", item_id)
        item = self._items.get(item_id)
        if item is None:
            raise ProviderError(f"Item not found: {item_id}")
        return item

    async def delete_item(self, item_id: str) -> None:
        self._record_operation("delete_item", item_id)
        self._items.pop(item_id, None)
