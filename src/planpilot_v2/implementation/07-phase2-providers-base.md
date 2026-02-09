# Phase 2: Providers Base

**Layer:** L2 (Core)
**Branch:** `v2/contracts` or `v2/github-provider`
**Phase:** 0 or 2
**Design doc:** [`../docs/modules/providers.md`](../docs/modules/providers.md)

---

## Files to Create

| File | Contents |
|------|----------|
| `providers/__init__.py` | Exports |
| `providers/base.py` | `ProviderContext` base class |
| `providers/factory.py` | `create_provider()` factory |
| `providers/dry_run.py` | `DryRunProvider` |

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
