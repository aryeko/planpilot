# Engine Module Spec

The engine module (`engine/`) orchestrates the sync pipeline. It receives a `Plan`, a `Provider`, and a `BodyRenderer` via dependency injection and runs a multi-phase sync that creates/updates work items in the external system.

The engine is the primary consumer of all Contracts (see [contracts.md](contracts.md) for type definitions).

## SyncEngine Class

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

The engine receives a fully constructed `Provider` (already authenticated via `__aenter__`), a `BodyRenderer`, config, and a `dry_run` flag. The `Plan` and its deterministic `plan_id` are passed to `sync()` — the SDK handles plan loading and hash computation.

### Concurrency Model

The engine processes item types sequentially (epics -> stories -> tasks) — parents must exist before children. Within each type level, operations are dispatched concurrently, gated by `asyncio.Semaphore(config.max_concurrent)`.

```python
self._semaphore = asyncio.Semaphore(config.max_concurrent)  # default 1 = sequential

async def _guarded(self, coro: Coroutine) -> T:
    async with self._semaphore:
        return await coro
```

The engine owns dispatch concurrency. The provider owns per-call reliability (retries, backoff). See [providers.md](../modules/providers.md) for the provider-side contract.

**`max_concurrent = 1` (default):** Fully sequential — safe, predictable, no concurrency edge cases.
**`max_concurrent > 1`:** Same-level operations run concurrently. Errors from any task fail the entire level (fail-fast via `asyncio.TaskGroup`).

## Sync Pipeline

```mermaid
flowchart TB
    subgraph Discovery["Phase 1: Discovery"]
        D1["provider.search_items(label + PLAN_ID)"]
        D2["parse metadata blocks from Item.body"]
        D3["build existing_map: dict[item_id, Item]"]
        D1 --> D2 --> D3
    end

    subgraph Upsert["Phase 2: Upsert"]
        U1["for each type level (epics -> stories -> tasks):"]
        U2["concurrent within level (semaphore-gated)"]
        U3{"item in existing_map?"}
        U4["skip create"]
        U5["provider.create_item(CreateItemInput)"]
        U6["sync_map.entries[item.id] = to_sync_entry(item)"]
        U1 --> U2 --> U3
        U3 -- Yes --> U4 --> U6
        U3 -- No --> U5 --> U6
    end

    subgraph Enrich["Phase 3: Enrich"]
        E1["all items concurrent (semaphore-gated)"]
        E2["renderer.render(item, full RenderContext)"]
        E3["provider.update_item(id, UpdateItemInput)"]
        E1 --> E2 --> E3
    end

    subgraph Relations["Phase 4: Relations"]
        R1["all relations concurrent (semaphore-gated)"]
        R2["item.set_parent / item.add_dependency"]
        R3["includes parent roll-ups"]
        R1 --> R2 --> R3
    end

    subgraph Result["Phase 5: Result"]
        RT["return SyncResult(sync_map, items_created, dry_run)"]
    end

    Discovery --> Upsert --> Enrich --> Relations --> Result
```

In dry-run mode, only Upsert runs (with placeholder entries, no API calls). Discovery, Enrich, and Relations are skipped. The SDK persists dry-run output to `<sync_path>.dry-run`.

## Phase 1: Discovery

**Goal:** Find items that already exist in the provider for this plan, so we can skip re-creating them.

**Source of truth:** Provider-search-first. The sync map is persisted output/cache, not the canonical source for finding existing items.

```python
filters = ItemSearchFilters(
    labels=[config.label],
    body_contains=f"PLAN_ID:{plan_id}",
)
existing_items: list[Item] = await provider.search_items(filters)
```

The engine parses the metadata block from each `Item.body` to extract `plan_id` and `item_id`. Items whose `plan_id` matches are indexed into `existing_map: dict[str, Item]`.

**Capability requirement:** Providers must support discovery filters (`labels` + `body_contains`). If unsupported, provider setup fails fast with `ProviderCapabilityError`.

**Metadata marker (renderer-agnostic):**

```text
PLANPILOT_META_V1
PLAN_ID:<plan_id>
ITEM_ID:<item_id>
END_PLANPILOT_META
```

This block must appear verbatim at the top of rendered item bodies for all renderers.

## Phase 2: Upsert

**Goal:** For each PlanItem, create it if it doesn't exist.

**Processing order:** By type level — epics first, then stories, then tasks. Within each level, items are dispatched concurrently (gated by `max_concurrent`).

```python
for item_type in [PlanItemType.EPIC, PlanItemType.STORY, PlanItemType.TASK]:
    level_items = [i for i in plan.items if i.type == item_type]

    async with asyncio.TaskGroup() as tg:
        for plan_item in level_items:
            tg.create_task(self._upsert_item(plan_item, plan_id))

async def _upsert_item(self, plan_item: PlanItem, plan_id: str) -> None:
    context = RenderContext(
        plan_id=plan_id,
        parent_ref=parent_entry.key,
        sub_items=[],
        dependencies={},
    )
    body = renderer.render(plan_item, context)

    if plan_item.id in existing_map:
        item = existing_map[plan_item.id]
    else:
        async with self._semaphore:
            try:
                item = await provider.create_item(input)
            except CreateItemPartialFailureError as exc:
                raise SyncError(...) from exc

    sync_map.entries[plan_item.id] = to_sync_entry(item)
```

**Failure semantics:** `asyncio.TaskGroup` propagates the first exception and cancels remaining tasks in the level (fail-fast). Partially created items are recoverable on next sync via Discovery.

**Dry-run behavior:** Skips all provider calls and creates placeholder `SyncEntry` objects with `key="dry-run"`, `url="dry-run"`.

## Phase 3: Enrich

**Goal:** Reconcile existing items with plan-authoritative fields (now that all items exist and have keys).

All items are enriched concurrently (gated by `max_concurrent`), regardless of type level — all keys are resolved by this point.

```python
async with asyncio.TaskGroup() as tg:
    for plan_item in plan.items:
        tg.create_task(self._enrich_item(plan_item, plan_id))

async def _enrich_item(self, plan_item: PlanItem, plan_id: str) -> None:
    context = RenderContext(
        plan_id=plan_id,
        parent_ref=parent_entry.key,
        sub_items=sorted([(child_entry.key, child_item.title) for child in children], key=lambda p: (p[0], p[1])),
        dependencies={dep_id: sync_map.entries[dep_id].key for dep_id in sorted(plan_item.depends_on)},
    )
    body = renderer.render(plan_item, context)

    async with self._semaphore:
        await provider.update_item(entry.id, UpdateItemInput(
            title=plan_item.title, body=body, item_type=plan_item.type,
            labels=[config.label],
            size=plan_item.estimate.tshirt if plan_item.estimate else None,
        ))
```

**Reconciliation ownership:**
- **Plan-authoritative:** `title`, `body`, `item_type`, `labels`, `size`, relations
- **Labels:** Additive (`ensure config.label present`), not replace-all
- **Provider-authoritative after create:** `status`, `priority`, `iteration` — not overwritten by Enrich

## Phase 4: Relations

**Goal:** Set up parent/child hierarchy and blocked-by dependency links.

Relation calls are dispatched concurrently (gated by `max_concurrent`). Parent and dependency relations are independent and can be set in any order.

```python
async with asyncio.TaskGroup() as tg:
    for item, parent_item in parent_pairs:
        tg.create_task(self._guarded(item.set_parent(parent_item)))
    for item, blocker_item in dependency_pairs:
        tg.create_task(self._guarded(item.add_dependency(blocker_item)))
```

**Roll-up logic:** If a child in parent A depends on a child in parent B (A != B), then parent A is blocked by parent B. This rolls up recursively (task deps -> story level, story deps -> epic level). Cyclic edges are de-duplicated and skipped with warnings.

**Note:** The engine stores `Item` objects (not just `SyncEntry`) during upsert for use in relation calls.

## Phase 5: Result

The engine returns `SyncResult` and does **not** persist the sync map to disk — that is the SDK's responsibility.

```python
return SyncResult(sync_map=sync_map, items_created=counters, dry_run=self._dry_run)
```

Sync map persistence (apply mode -> `config.sync_path`, dry-run -> `<sync_path>.dry-run`) is handled by the SDK.

## Sync Map Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Empty: engine starts
    Empty --> Populated: Discovery indexes existing items
    Populated --> Updated: Upsert adds new entries
    Updated --> Enriched: Enrich updates bodies with cross-refs
    Enriched --> Returned: engine returns SyncResult
    Returned --> Persisted: SDK writes to disk
```

## Internal Utilities

| Utility | Signature | Purpose |
|---------|-----------|---------|
| `parse_metadata_block` | `(body: str) -> dict[str, str]` | Extract PLAN_ID, ITEM_ID from metadata block |
| `compute_parent_blocked_by` | `(items: list[PlanItem], item_type: PlanItemType) -> set[tuple[str, str]]` | Roll up child deps to parent level |
