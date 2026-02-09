import pytest

from planpilot.contracts.exceptions import ProviderError
from planpilot.contracts.item import CreateItemInput, UpdateItemInput
from planpilot.contracts.plan import PlanItemType
from planpilot.providers.dry_run import DryRunItem, DryRunProvider


@pytest.mark.asyncio
async def test_dry_run_provider_create_update_get_are_deterministic() -> None:
    provider = DryRunProvider()

    created = await provider.create_item(CreateItemInput(title="Task", body="body", item_type=PlanItemType.TASK))

    assert created.id == "dry-run-1"
    assert created.key == "dry-run"
    assert created.url == "dry-run"
    assert created.title == "Task"
    assert created.body == "body"
    assert created.item_type == PlanItemType.TASK

    updated = await provider.update_item(created.id, UpdateItemInput(title="Task2", body="body2"))
    assert updated.id == created.id
    assert updated.title == "Task2"
    assert updated.body == "body2"

    fetched = await provider.get_item(created.id)
    assert fetched.title == "Task2"


@pytest.mark.asyncio
async def test_dry_run_item_relations_are_logged_with_monotonic_sequence() -> None:
    provider = DryRunProvider()
    parent = DryRunItem(id="p", title="Parent", body="", item_type=PlanItemType.EPIC)
    child = await provider.create_item(CreateItemInput(title="Child", body="", item_type=PlanItemType.STORY))

    await child.set_parent(parent)
    await child.add_dependency(parent)

    assert child.id == "dry-run-1"
    assert [operation.sequence for operation in provider.operations] == [1, 2, 3]
    assert [operation.name for operation in provider.operations] == [
        "create_item",
        "set_parent",
        "add_dependency",
    ]
    assert [operation.item_id for operation in provider.operations] == ["dry-run-1", "dry-run-1", "dry-run-1"]
    assert provider.operations[0].payload == {"title": "Child", "item_type": "STORY"}
    assert provider.operations[1].payload == {"parent_id": "p"}
    assert provider.operations[2].payload == {"blocker_id": "p"}


@pytest.mark.asyncio
async def test_dry_run_provider_search_is_empty_and_delete_is_noop() -> None:
    provider = DryRunProvider()

    matched = await provider.search_items(filters={})  # type: ignore[arg-type]
    assert matched == []

    await provider.delete_item("missing")


@pytest.mark.asyncio
async def test_dry_run_provider_missing_item_operations_raise() -> None:
    provider = DryRunProvider()

    with pytest.raises(ProviderError):
        await provider.get_item("missing")

    with pytest.raises(ProviderError):
        await provider.update_item("missing", UpdateItemInput(title="x"))

    assert [operation.sequence for operation in provider.operations] == [1, 2]
    assert [operation.name for operation in provider.operations] == ["get_item", "update_item"]
    assert [operation.item_id for operation in provider.operations] == ["missing", "missing"]
    assert provider.operations[0].payload == {}
    assert provider.operations[1].payload == {"title": "x"}


@pytest.mark.asyncio
async def test_dry_run_provider_context_manager() -> None:
    async with DryRunProvider() as provider:
        assert isinstance(provider, DryRunProvider)
