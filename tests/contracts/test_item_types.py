from planpilot.core.contracts.item import CreateItemInput, ItemSearchFilters, UpdateItemInput
from planpilot.core.contracts.plan import PlanItemType


def test_create_item_input_defaults() -> None:
    item = CreateItemInput(title="Title", body="Body", item_type=PlanItemType.STORY)

    assert item.labels == []
    assert item.size is None


def test_update_item_input_defaults() -> None:
    item = UpdateItemInput()

    assert item.title is None
    assert item.body is None
    assert item.item_type is None
    assert item.labels is None
    assert item.size is None


def test_item_search_filters_defaults() -> None:
    filters = ItemSearchFilters()

    assert filters.labels == []
    assert filters.body_contains == ""
