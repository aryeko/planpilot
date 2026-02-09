from planpilot_v2.contracts.item import Item
from planpilot_v2.contracts.plan import PlanItemType
from planpilot_v2.contracts.sync import SyncMap, to_sync_entry


class DummyItem(Item):
    @property
    def id(self) -> str:
        return "node-1"

    @property
    def key(self) -> str:
        return "#1"

    @property
    def url(self) -> str:
        return "https://example/items/1"

    @property
    def title(self) -> str:
        return "Title"

    @property
    def body(self) -> str:
        return "Body"

    @property
    def item_type(self) -> PlanItemType | None:
        return PlanItemType.TASK

    async def set_parent(self, parent: Item) -> None:
        return None

    async def add_dependency(self, blocker: Item) -> None:
        return None


def test_to_sync_entry_maps_provider_item_fields() -> None:
    entry = to_sync_entry(DummyItem())

    assert entry.id == "node-1"
    assert entry.key == "#1"
    assert entry.url == "https://example/items/1"
    assert entry.item_type == PlanItemType.TASK


def test_sync_map_mutable_defaults_are_not_shared() -> None:
    first = SyncMap(plan_id="p1", target="owner/repo", board_url="https://example/board")
    second = SyncMap(plan_id="p2", target="owner/repo", board_url="https://example/board")

    first.entries["A"] = to_sync_entry(DummyItem())

    assert second.entries == {}
