import pytest

from planpilot_v2.contracts.exceptions import ProviderError
from planpilot_v2.contracts.item import CreateItemInput, ItemSearchFilters, UpdateItemInput
from planpilot_v2.contracts.plan import PlanItemType
from planpilot_v2.contracts.provider import Provider
from tests.v2.fakes.provider import FakeProvider


@pytest.mark.asyncio
async def test_fake_provider_implements_provider_contract() -> None:
    provider = FakeProvider()

    assert isinstance(provider, Provider)


@pytest.mark.asyncio
async def test_fake_provider_create_update_search_delete_flow() -> None:
    provider = FakeProvider()

    created = await provider.create_item(
        CreateItemInput(
            title="Task one",
            body="body text PLAN_ID:abc",
            item_type=PlanItemType.TASK,
            labels=["planpilot", "task"],
        )
    )

    assert created.id == "fake-id-1"
    assert created.key == "#1"
    assert created.url == "https://fake/issues/1"

    updated = await provider.update_item(
        created.id,
        UpdateItemInput(title="Task one updated", labels=["planpilot"]),
    )
    assert updated.title == "Task one updated"

    matched = await provider.search_items(ItemSearchFilters(labels=["planpilot"], body_contains="PLAN_ID:abc"))
    assert [item.id for item in matched] == [created.id]

    await provider.delete_item(created.id)
    with pytest.raises(ProviderError):
        await provider.get_item(created.id)


@pytest.mark.asyncio
async def test_fake_provider_records_parent_and_dependency_relations() -> None:
    provider = FakeProvider()
    parent = await provider.create_item(CreateItemInput(title="Parent", body="", item_type=PlanItemType.EPIC))
    child = await provider.create_item(CreateItemInput(title="Child", body="", item_type=PlanItemType.STORY))
    blocker = await provider.create_item(CreateItemInput(title="Blocker", body="", item_type=PlanItemType.TASK))

    await child.set_parent(parent)
    await child.add_dependency(blocker)

    assert provider.parents[child.id] == parent.id
    assert provider.dependencies[child.id] == {blocker.id}
