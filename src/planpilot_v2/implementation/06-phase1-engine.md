# Phase 1: Engine Module

**Layer:** L2 (Core)
**Branch:** `v2/engine`
**Phase:** 1 (parallel with plan, auth, renderers)
**Dependencies:** Contracts only (`planpilot_v2.contracts.*`)
**Design doc:** [`../docs/design/engine.md`](../docs/design/engine.md)

---

## Files to Create

| File | Contents |
|------|----------|
| `engine/__init__.py` | Exports `SyncEngine` |
| `engine/engine.py` | `SyncEngine` class |
| `engine/utils.py` | `parse_metadata_block()`, `compute_parent_blocked_by()` |

---

## SyncEngine

```python
class SyncEngine:
    def __init__(
        self,
        provider: Provider,
        renderer: BodyRenderer,
        config: PlanPilotConfig,
        *,
        dry_run: bool = False,
    ) -> None: ...

    async def sync(self, plan: Plan, plan_id: str) -> SyncResult: ...
```

---

## 5-Phase Pipeline

### Phase 1 — Discovery

Find existing items via `provider.search_items()`, parse metadata blocks, build `existing_map: dict[str, Item]`.

```python
filters = ItemSearchFilters(
    labels=[config.label],
    body_contains=f"PLAN_ID:{plan_id}",
)
existing_items = await provider.search_items(filters)
# Parse metadata block from each item.body to extract item_id
# Build existing_map keyed by item_id
```

### Phase 2 — Upsert

For each type level (EPIC -> STORY -> TASK), create items not in `existing_map`. Concurrent within level via `asyncio.Semaphore(config.max_concurrent)` + `asyncio.TaskGroup`.

### Phase 3 — Enrich

Update all items with full cross-reference context (now that all keys exist). Concurrent, semaphore-gated.

### Phase 4 — Relations

Set parent/child and dependency links. Concurrent. Includes parent roll-up logic.

### Phase 5 — Result

Return `SyncResult(sync_map, items_created, dry_run)`.

### Dry-run Behavior

Dry-run executes the same 5-phase pipeline using an injected `DryRunProvider`, so discovery/upsert/enrich/relations logic is exercised end-to-end. No external API calls occur in dry-run mode.

---

## Concurrency Model

```python
self._semaphore = asyncio.Semaphore(config.max_concurrent)

async def _guarded(self, coro):
    async with self._semaphore:
        return await coro
```

Type levels are processed sequentially. Within each level, operations are concurrent. Errors fail-fast via `TaskGroup`.

---

## Engine Utilities

```python
def parse_metadata_block(body: str) -> dict[str, str]:
    """Extract PLAN_ID, ITEM_ID from PLANPILOT_META_V1 block."""

def compute_parent_blocked_by(
    items: list[PlanItem], item_type: PlanItemType,
) -> set[tuple[str, str]]:
    """Roll up child deps to parent level."""
```

---

## Test Strategy (uses FakeProvider + FakeRenderer)

| Test File | Key Cases |
|-----------|-----------|
| `test_engine.py` | **Discovery:** search_items called with correct filters, metadata parsed to build existing_map. **Upsert:** new items created via provider, existing items skipped, type-level ordering (epics before stories before tasks). **Enrich:** update_item called with full context, cross-refs resolved. **Relations:** set_parent/add_dependency called correctly, parent roll-up. **Dry-run:** full pipeline runs against `DryRunProvider` with no external API calls. **Concurrency:** semaphore respected. **Errors:** CreateItemPartialFailureError wrapped in SyncError. **Result:** SyncResult has correct counts and sync_map. |
