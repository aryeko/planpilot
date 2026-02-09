# Phase 2: Providers Base

**Layer:** L2 (Core)
**Branch:** `v2/github-provider`
**Phase:** 2 (after contracts)
**Design doc:** [`../docs/modules/providers.md`](../docs/modules/providers.md)

---

## Files to Create

| File | Contents |
|------|----------|
| `providers/__init__.py` | Exports |
| `providers/base.py` | `ProviderContext` base class |
| `providers/factory.py` | `create_provider()` factory |
| `providers/dry_run.py` | `DryRunItem`, `DryRunProvider` |

---

## ProviderContext

```python
class ProviderContext:
    """Base class for provider-specific resolved state. Opaque to engine/SDK."""
    pass
```

---

## Provider Factory

```python
PROVIDERS: dict[str, type[Provider]] = {
    "github": GitHubProvider,
}

def create_provider(
    name: str, *, target: str, token: str, board_url: str,
    label: str = "planpilot", field_config: FieldConfig | None = None,
    **kwargs: object,
) -> Provider:
    """Create a provider instance by name.
    Raises: ValueError if unknown.
    """
```

---

## DryRunProvider

In-memory provider for `sync(dry_run=True)`. No auth, no network.

```python
class DryRunItem(Item):
    """Placeholder item returned by DryRunProvider. Defined in providers/dry_run.py."""

    def __init__(self, *, id: str, title: str, body: str,
                 item_type: PlanItemType | None) -> None: ...

    @property
    def id(self) -> str: ...
    @property
    def key(self) -> str: return "dry-run"
    @property
    def url(self) -> str: return "dry-run"
    @property
    def title(self) -> str: ...
    @property
    def body(self) -> str: ...
    @property
    def item_type(self) -> PlanItemType | None: ...

    async def set_parent(self, parent: Item) -> None: pass   # no-op
    async def add_dependency(self, blocker: Item) -> None: pass  # no-op


class DryRunProvider(Provider):
    """Provider that returns deterministic placeholders. No network calls."""

    async def __aenter__(self) -> "DryRunProvider": return self
    async def __aexit__(self, *args) -> None: pass
    async def search_items(self, filters) -> list[Item]: return []
    async def create_item(self, input) -> Item:
        # Return DryRunItem with key="dry-run", url="dry-run"
    async def update_item(self, item_id, input) -> Item: ...
    async def get_item(self, item_id) -> Item: ...
    async def delete_item(self, item_id) -> None: pass
```
