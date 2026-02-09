# Phase 0: Contracts

> Foundation layer — must be completed before all other phases.

**Layer:** L1 (Contracts)
**Branch:** `v2/contracts`
**Dependencies:** None (stdlib + pydantic only)
**Design doc:** [`../docs/design/contracts.md`](../docs/design/contracts.md)

---

## Files to Create

| File | Contents |
|------|----------|
| `contracts/__init__.py` | Re-export all public types |
| `contracts/plan.py` | `PlanItemType`, `PlanItem`, `Plan`, `Scope`, `SpecRef`, `Estimate`, `Verification` |
| `contracts/item.py` | `Item` ABC, `CreateItemInput`, `UpdateItemInput`, `ItemSearchFilters` |
| `contracts/sync.py` | `SyncEntry`, `SyncMap`, `SyncResult`, `to_sync_entry()` |
| `contracts/config.py` | `PlanPilotConfig`, `PlanPaths`, `FieldConfig` |
| `contracts/provider.py` | `Provider` ABC |
| `contracts/renderer.py` | `BodyRenderer` ABC, `RenderContext` |
| `contracts/exceptions.py` | Full exception hierarchy |

## Domain Dependency Order

```text
plan domain          (no dependencies)
├── item domain      (uses PlanItemType from plan)
│   ├── provider domain   (uses Item, inputs from item)
│   └── sync domain       (uses Item from item)
└── renderer domain  (uses PlanItem from plan)

config domain        (no dependencies)
exceptions           (no dependencies)
```

---

## contracts/plan.py

```python
from enum import Enum
from pydantic import BaseModel


class PlanItemType(str, Enum):
    EPIC = "EPIC"
    STORY = "STORY"
    TASK = "TASK"


class Scope(BaseModel):
    in_scope: list[str] = []
    out_scope: list[str] = []


class SpecRef(BaseModel):
    url: str
    section: str | None = None
    quote: str | None = None


class Estimate(BaseModel):
    tshirt: str | None = None
    hours: float | None = None


class Verification(BaseModel):
    commands: list[str] = []
    ci_checks: list[str] = []
    evidence: list[str] = []
    manual_steps: list[str] = []


class PlanItem(BaseModel):
    id: str
    type: PlanItemType
    title: str
    goal: str | None = None
    motivation: str | None = None
    parent_id: str | None = None
    sub_item_ids: list[str] = []
    depends_on: list[str] = []
    requirements: list[str] = []
    acceptance_criteria: list[str] = []
    success_metrics: list[str] = []
    assumptions: list[str] = []
    risks: list[str] = []
    estimate: Estimate | None = None
    verification: Verification | None = None
    spec_ref: SpecRef | None = None
    scope: Scope | None = None


class Plan(BaseModel):
    items: list[PlanItem]
```

---

## contracts/item.py

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel
from planpilot_v2.contracts.plan import PlanItemType


class Item(ABC):
    """Provider-agnostic work item."""

    @property
    @abstractmethod
    def id(self) -> str: ...          # Provider-internal ID (e.g. node_id)

    @property
    @abstractmethod
    def key(self) -> str: ...         # Human-readable key (e.g. "#42", "PROJ-123")

    @property
    @abstractmethod
    def url(self) -> str: ...         # Full URL to the item

    @property
    @abstractmethod
    def title(self) -> str: ...

    @property
    @abstractmethod
    def body(self) -> str: ...

    @property
    @abstractmethod
    def item_type(self) -> PlanItemType | None: ...

    @abstractmethod
    async def set_parent(self, parent: "Item") -> None: ...

    @abstractmethod
    async def add_dependency(self, blocker: "Item") -> None: ...


class CreateItemInput(BaseModel):
    title: str
    body: str
    item_type: PlanItemType
    labels: list[str] = []
    size: str | None = None


class UpdateItemInput(BaseModel):
    title: str | None = None
    body: str | None = None
    item_type: PlanItemType | None = None
    labels: list[str] | None = None
    size: str | None = None


class ItemSearchFilters(BaseModel):
    labels: list[str] = []
    body_contains: str = ""
```

---

## contracts/sync.py

```python
from pydantic import BaseModel
from planpilot_v2.contracts.plan import PlanItemType
from planpilot_v2.contracts.item import Item


class SyncEntry(BaseModel):
    id: str
    key: str
    url: str
    item_type: PlanItemType | None = None


class SyncMap(BaseModel):
    plan_id: str
    target: str
    board_url: str
    entries: dict[str, SyncEntry] = {}


class SyncResult(BaseModel):
    sync_map: SyncMap
    items_created: dict[PlanItemType, int] = {}
    dry_run: bool = False


def to_sync_entry(item: Item) -> SyncEntry:
    """Convert a provider Item to a SyncEntry for persistence."""
    return SyncEntry(id=item.id, key=item.key, url=item.url, item_type=item.item_type)
```

---

## contracts/config.py

```python
from pathlib import Path
from pydantic import BaseModel, Field


class FieldConfig(BaseModel):
    status: str = "Backlog"
    priority: str = "P1"
    iteration: str = "active"
    size_field: str = "Size"
    size_from_tshirt: bool = True
    create_type_strategy: str = "issue-type"
    create_type_map: dict[str, str] = {"EPIC": "Epic", "STORY": "Story", "TASK": "Task"}


class PlanPaths(BaseModel):
    epics: Path | None = None
    stories: Path | None = None
    tasks: Path | None = None
    unified: Path | None = None


class PlanPilotConfig(BaseModel):
    provider: str
    target: str
    auth: str = "gh-cli"
    token: str | None = None
    board_url: str
    plan_paths: PlanPaths
    validation_mode: str = "strict"
    sync_path: Path = Path("sync-map.json")
    label: str = "planpilot"
    max_concurrent: int = Field(default=1, ge=1, le=10)
    field_config: FieldConfig = FieldConfig()

    model_config = {"frozen": True}
```

**PlanPaths validation rules:**
- If `unified` is set, none of `epics`/`stories`/`tasks` may be set
- At least one of the four fields must be non-None

**Auth/Token validation rules:**

| `auth` value | `token` value | Result |
|--------------|---------------|--------|
| `"gh-cli"` | `None` | Valid |
| `"env"` | `None` | Valid |
| `"token"` | non-empty string | Valid |
| `"token"` | `None` / empty | Invalid (`ConfigError`) |
| `"gh-cli"` or `"env"` | non-empty string | Invalid (`ConfigError`) |

---

## contracts/provider.py

```python
from abc import ABC, abstractmethod
from planpilot_v2.contracts.item import Item, CreateItemInput, UpdateItemInput, ItemSearchFilters


class Provider(ABC):
    @abstractmethod
    async def __aenter__(self) -> "Provider": ...

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None: ...

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
```

---

## contracts/renderer.py

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel
from planpilot_v2.contracts.plan import PlanItem


class RenderContext(BaseModel):
    plan_id: str
    parent_ref: str | None = None
    sub_items: list[tuple[str, str]] = []       # (key, title) pairs
    dependencies: dict[str, str] = {}           # {dep_id: issue_ref}


class BodyRenderer(ABC):
    @abstractmethod
    def render(self, item: PlanItem, context: RenderContext) -> str: ...
```

---

## contracts/exceptions.py

```python
class PlanPilotError(Exception):
    """Base exception for all PlanPilot errors."""


class ConfigError(PlanPilotError):
    """Configuration loading or validation failure."""


class PlanLoadError(PlanPilotError):
    """File I/O or JSON parse failure during plan loading."""


class PlanValidationError(PlanPilotError):
    """Relational integrity validation failure."""
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"Plan validation failed with {len(errors)} error(s): {'; '.join(errors)}")


class ProviderError(PlanPilotError):
    """Provider operation failure."""


class ProviderCapabilityError(ProviderError):
    """Provider does not support a required capability."""
    def __init__(self, capability: str) -> None:
        self.capability = capability
        super().__init__(f"Provider does not support: {capability}")


class CreateItemPartialFailureError(ProviderError):
    """create_item() failed after partial completion."""
    def __init__(
        self, *,
        created_item_id: str | None = None,
        created_item_key: str | None = None,
        created_item_url: str | None = None,
        completed_steps: tuple[str, ...] = (),
        retryable: bool = False,
        message: str = "create_item partially failed",
    ) -> None:
        self.created_item_id = created_item_id
        self.created_item_key = created_item_key
        self.created_item_url = created_item_url
        self.completed_steps = completed_steps
        self.retryable = retryable
        super().__init__(message)


class AuthenticationError(ProviderError):
    """Authentication/token resolution failure."""


class ProjectURLError(ProviderError):
    """Invalid project board URL."""


class SyncError(PlanPilotError):
    """Non-recoverable sync/reconciliation failure."""
```

---

## Test Strategy

| Test File | Key Cases |
|-----------|-----------|
| `test_plan_types.py` | PlanItem creation, PlanItemType enum values, Plan with items, Scope/SpecRef/Estimate/Verification defaults |
| `test_item_types.py` | CreateItemInput validation, UpdateItemInput optional fields, ItemSearchFilters defaults |
| `test_sync_types.py` | SyncEntry creation, SyncMap with entries, SyncResult, `to_sync_entry()` conversion |
| `test_config_types.py` | PlanPilotConfig frozen, PlanPaths mutual exclusivity, FieldConfig defaults, auth/token validation |
| `test_exceptions.py` | Hierarchy (`isinstance` checks), PlanValidationError.errors, CreateItemPartialFailureError fields |
