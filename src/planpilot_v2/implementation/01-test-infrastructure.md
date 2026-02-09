# Shared Test Infrastructure

> FakeProvider, FakeRenderer, and shared conftest fixtures used across multiple test suites.
> Created in Phase 0 alongside contracts.

## FakeProvider (`tests/v2/fakes/provider.py`)

In-memory provider for testing engine, SDK, and integration scenarios. Must implement the full `Provider` ABC.

```python
from planpilot_v2.contracts.item import Item, CreateItemInput, UpdateItemInput, ItemSearchFilters
from planpilot_v2.contracts.plan import PlanItemType
from planpilot_v2.contracts.provider import Provider


class FakeItem(Item):
    """In-memory Item with relation tracking."""

    def __init__(
        self, *, id: str, key: str, url: str, title: str, body: str,
        item_type: PlanItemType | None, provider: "FakeProvider",
    ) -> None: ...

    @property
    def id(self) -> str: ...
    @property
    def key(self) -> str: ...
    @property
    def url(self) -> str: ...
    @property
    def title(self) -> str: ...
    @property
    def body(self) -> str: ...
    @property
    def item_type(self) -> PlanItemType | None: ...

    async def set_parent(self, parent: Item) -> None:
        """Record parent relation in provider's relation store."""

    async def add_dependency(self, blocker: Item) -> None:
        """Record dependency in provider's relation store."""


class FakeProvider(Provider):
    """In-memory provider. Deterministic IDs, no network, spy tracking."""

    def __init__(self) -> None:
        self.items: dict[str, FakeItem] = {}
        self.parents: dict[str, str] = {}           # child_id -> parent_id
        self.dependencies: dict[str, set[str]] = {}  # item_id -> {blocker_ids}
        self._next_number: int = 1

        # Spy lists for assertions
        self.search_calls: list[ItemSearchFilters] = []
        self.create_calls: list[CreateItemInput] = []
        self.update_calls: list[tuple[str, UpdateItemInput]] = []
        self.delete_calls: list[str] = []

    async def __aenter__(self) -> "FakeProvider":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    async def search_items(self, filters: ItemSearchFilters) -> list[Item]:
        """Return items matching filters. Records call in search_calls."""
        # Filter by label AND body_contains (conjunctive)
        # Return matching items from self.items

    async def create_item(self, input: CreateItemInput) -> Item:
        """Create item with deterministic ID/key/url. Records call."""
        # Assign id=f"fake-id-{n}", key=f"#{n}", url=f"https://fake/issues/{n}"
        # Increment self._next_number
        # Store in self.items

    async def update_item(self, item_id: str, input: UpdateItemInput) -> Item:
        """Update item fields. Records call."""
        # Apply non-None fields to existing item

    async def get_item(self, item_id: str) -> Item:
        """Return item by ID. Raise ProviderError if missing."""

    async def delete_item(self, item_id: str) -> None:
        """Remove item. Records call."""
```

### Behavior Rules

- Deterministic: same inputs produce same outputs
- `search_items` filters by `labels` AND `body_contains` conjunctively
- `create_item` auto-assigns incrementing IDs (`fake-id-1`, `fake-id-2`, ...)
- `create_item` auto-assigns keys (`#1`, `#2`, ...) and URLs
- Spy lists record every call for assertion in tests
- `set_parent` / `add_dependency` record relations in the provider's stores

---

## FakeRenderer (`tests/v2/fakes/renderer.py`)

Deterministic renderer that produces the required metadata block plus minimal structured output.

```python
from planpilot_v2.contracts.plan import PlanItem
from planpilot_v2.contracts.renderer import BodyRenderer, RenderContext


class FakeRenderer(BodyRenderer):
    """Deterministic renderer for testing."""

    def render(self, item: PlanItem, context: RenderContext) -> str:
        """Emit metadata block + minimal body."""
        lines = [
            "PLANPILOT_META_V1",
            f"PLAN_ID:{context.plan_id}",
            f"ITEM_ID:{item.id}",
            "END_PLANPILOT_META",
            "",
            f"# {item.title}",
        ]
        if context.parent_ref:
            lines.append(f"Parent: {context.parent_ref}")
        for key, title in context.sub_items:
            lines.append(f"Sub: {key} {title}")
        for dep_id, ref in sorted(context.dependencies.items()):
            lines.append(f"Dep: {ref}")
        return "\n".join(lines)
```

---

## Shared Fixtures (`tests/v2/conftest.py`)

```python
import pytest
from planpilot_v2.contracts.plan import PlanItem, PlanItemType, Plan
from planpilot_v2.contracts.config import PlanPilotConfig, PlanPaths, FieldConfig


@pytest.fixture
def sample_epic() -> PlanItem:
    return PlanItem(
        id="E1", type=PlanItemType.EPIC, title="Epic One",
        goal="Deliver feature X",
        requirements=["R1"], acceptance_criteria=["AC1"],
        sub_item_ids=["S1"],
    )

@pytest.fixture
def sample_story() -> PlanItem:
    return PlanItem(
        id="S1", type=PlanItemType.STORY, title="Story One",
        goal="Implement part A", parent_id="E1",
        requirements=["R1"], acceptance_criteria=["AC1"],
        sub_item_ids=["T1"],
    )

@pytest.fixture
def sample_task() -> PlanItem:
    return PlanItem(
        id="T1", type=PlanItemType.TASK, title="Task One",
        goal="Code module A", parent_id="S1",
        requirements=["R1"], acceptance_criteria=["AC1"],
    )

@pytest.fixture
def sample_plan(sample_epic, sample_story, sample_task) -> Plan:
    return Plan(items=[sample_epic, sample_story, sample_task])

@pytest.fixture
def sample_config(tmp_path) -> PlanPilotConfig:
    return PlanPilotConfig(
        provider="github",
        target="owner/repo",
        board_url="https://github.com/orgs/owner/projects/1",
        plan_paths=PlanPaths(unified=tmp_path / "plan.json"),
        sync_path=tmp_path / "sync-map.json",
    )
```
