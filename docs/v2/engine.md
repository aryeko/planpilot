# Engine Module Spec

## Overview

The engine module (`engine/`) orchestrates the sync pipeline. It receives a `Plan`, a `Provider`, and a `BodyRenderer` via dependency injection and runs a multi-phase sync that creates/updates work items in the external system.

The engine is the primary consumer of all Contracts. Every contract type used below is defined in the Contracts layer.

## Dependencies (Contracts only)

| Contract Domain | Types Used |
|----------------|-----------|
| **plan** | `Plan`, `PlanItem`, `PlanItemType` |
| **item** | `Item`, `CreateItemInput`, `UpdateItemInput`, `ItemSearchFilters` |
| **sync** | `SyncEntry`, `SyncMap`, `SyncResult`, `to_sync_entry()` |
| **config** | `PlanPilotConfig` |
| **provider** | `Provider` ABC |
| **renderer** | `BodyRenderer` ABC, `RenderContext` |
| **exceptions** | `SyncError`, `CreateItemPartialFailureError` |

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

The engine receives a fully constructed `Provider` (already authenticated via `__aenter__`), a `BodyRenderer`, config, and a `dry_run` flag. The `Plan` and its deterministic `plan_id` are passed to `sync()` — the SDK handles plan loading and hash computation (via `PlanHasher`). `dry_run` is a runtime execution mode passed by the SDK, not part of the persisted config.

### Sync Pipeline

```mermaid
flowchart LR
    Discovery --> Upsert --> Enrich --> Relations --> Result
```

In dry-run mode, only Upsert runs (with placeholder entries, no API calls). Discovery, Enrich, and Relations are skipped.

## Phase 1: Discovery

**Goal:** Find items that already exist in the provider for this plan, so we can skip re-creating them.

**Source of truth:** Discovery is provider-search-first. The sync map is persisted output/cache, not the canonical source for finding existing items.

**Capability requirement:** providers must support Discovery filters (`labels` + `body_contains`). If unsupported, provider setup fails fast with `ProviderCapabilityError`.

**Contract calls:**

```python
filters = ItemSearchFilters(
    labels=[config.label],
    body_contains=f"PLAN_ID:{plan_id}",
)
existing_items: list[Item] = await provider.search_items(filters)
```

**Internal logic:**

The engine parses the metadata block from each `Item.body` to extract `plan_id` and `item_id`. Items whose `plan_id` matches are indexed into a lookup dict:

```python
existing_map: dict[str, Item]
# {item_id: Item, ...}
```

**Contract types required:**
- `ItemSearchFilters` — needs `labels: list[str]`, `body_contains: str`
- `Item` — needs `id`, `key`, `url`, `body` fields
- `Provider.search_items(ItemSearchFilters) -> list[Item]`

**Internal utilities:**
- `parse_metadata_block(body: str) -> dict[str, str]` — extracts metadata block keys (`PLAN_ID`, `ITEM_ID`) from body text. This is an engine-internal utility, not a contract.

**Marker contract used by discovery (renderer-agnostic):**

```text
PLANPILOT_META_V1
PLAN_ID:<plan_id>
ITEM_ID:<item_id>
END_PLANPILOT_META
```

The block must appear verbatim at the top of rendered item bodies for all renderers.

## Phase 2: Upsert

**Goal:** For each PlanItem (epic, story, task) in the plan, create it if it doesn't exist.

**Processing order:** Items are topologically sorted so that parents are created before children. The engine sorts by type level (epics → stories → tasks) and then by `parent_id` within each level, ensuring a parent item is always created before any item that references it.

**Contract calls per item:**

```python
# 1. Build render context
context = RenderContext(
    plan_id=plan_id,
    parent_ref=parent_entry.key,          # e.g. "#42"
    sub_items=[],                          # empty on first pass
    dependencies={},                       # empty on first pass
)

# 2. Render body
body: str = renderer.render(plan_item, context)

# 3. Upsert branch
if plan_item.id in existing_map:
    # Existing item discovered by provider-search-first Discovery.
    item = existing_map[plan_item.id]
else:
    input = CreateItemInput(
        title=plan_item.title,
        body=body,
        item_type=plan_item.type,             # PlanItemType enum
        labels=[config.label],
        size=plan_item.estimate.tshirt if plan_item.estimate else None,
    )
    try:
        item = await provider.create_item(input)
    except CreateItemPartialFailureError as exc:
        # Preserve deterministic retry by surfacing structured context.
        raise SyncError(
            f"partial create failure for {plan_item.id}: "
            f"created_item_id={exc.created_item_id!r} "
            f"steps={exc.completed_steps} retryable={exc.retryable}"
        ) from exc

# 4. Record in sync map
entry: SyncEntry = to_sync_entry(item)
sync_map.entries[plan_item.id] = entry
```

**Contract types required:**
- `RenderContext` — needs `plan_id: str`, `parent_ref: str | None`, `sub_items: list[tuple[str, str]]`, `dependencies: dict[str, str]`
- `BodyRenderer.render(PlanItem, RenderContext) -> str`
- `CreateItemInput` — needs `title: str`, `body: str`, `item_type: PlanItemType`, `labels: list[str]`, `size: str | None`
- `Provider.create_item(CreateItemInput) -> Item`
- `CreateItemPartialFailureError` — structured partial failure context from provider
- `to_sync_entry(Item) -> SyncEntry` — from sync domain
- `SyncMap` — flat `entries: dict[str, SyncEntry]` keyed by item ID

**Dry-run behavior:** In dry-run mode, the engine skips all provider calls and creates placeholder `SyncEntry` objects with `key="dry-run"`, `url="dry-run"`.

## Phase 3: Enrich

**Goal:** Reconcile existing items with plan-authoritative fields (now that all items exist and have keys).

**Contract calls per item:**

```python
# 1. Build full render context with resolved refs
context = RenderContext(
    plan_id=plan_id,
    parent_ref=parent_entry.key,
    sub_items=[(child_entry.key, child_item.title) for child in children],
    dependencies={dep_id: dep_entry.key for dep_id in plan_item.depends_on},
)

# 2. Re-render body with full cross-refs
body: str = renderer.render(plan_item, context)

# 3. Update the item
await provider.update_item(
    entry.id,
    UpdateItemInput(
        title=plan_item.title,
        body=body,
        item_type=plan_item.type,
        labels=[config.label],
        size=plan_item.estimate.tshirt if plan_item.estimate else None,
    ),
)
```

**Contract types required:**
- `RenderContext` — same as upsert, but now populated with resolved sub_items and dependencies
- `BodyRenderer.render(PlanItem, RenderContext) -> str`
- `UpdateItemInput` — needs `title`, `body`, `item_type`, `labels`, `size` fields (only non-None fields applied)
- `Provider.update_item(str, UpdateItemInput) -> Item`

**Ownership rule during reconcile:**
- Plan-authoritative fields: `title`, `body`, `item_type`, `labels`, `size`, and relations.
- `labels` are additive (`ensure config.label present`), not replace-all.
- Provider-authoritative fields after create: board workflow fields (`status`, `priority`, `iteration`) are not overwritten by Enrich.

## Phase 4: Relations

**Goal:** Set up parent/child hierarchy and blocked-by dependency links.

**Contract calls:**

```python
# Parent/child: set parent for items with parent_id
await item.set_parent(parent_item)

# Blocked-by: direct deps + parent-level roll-ups
await item.add_dependency(blocker_item)
```

**Internal logic:**

1. **Direct dependencies:** For each item with `depends_on`, call `add_dependency` for each referenced item.
2. **Parent hierarchy:** For each item with `parent_id`, call `set_parent` with the parent item.
3. **Parent roll-up:** If a child in parent A depends on a child in parent B (and A != B), then parent A is blocked by parent B. This rolls up recursively through the hierarchy (e.g. task deps roll up to story level, story deps roll up to epic level).
4. **Cycle handling:** Roll-up edges are de-duplicated and cycle-checked before relation calls. Cyclic edges are skipped and surfaced as warnings in the sync result summary.

Roll-up is computed by engine-internal utilities:

```python
def compute_parent_blocked_by(
    items: list[PlanItem],
    item_type: PlanItemType,
) -> set[tuple[str, str]]:
    """Compute parent-level blocked-by from child dependencies."""
```

**Contract types required:**
- `Item.set_parent(Item) -> None` — sets parent/child relationship
- `Item.add_dependency(Item) -> None` — sets blocked-by relationship

**Note:** The engine needs `Item` objects (not just `SyncEntry`) for relation calls. During upsert, the engine stores `Item` objects alongside `SyncEntry` entries for use in this phase.

## Phase 5: Result

**Goal:** Build and return the sync result. The engine does **not** persist the sync map to disk — that is the SDK's responsibility.

```python
return SyncResult(
    sync_map=sync_map,
    items_created=counters,  # dict[PlanItemType, int]
    dry_run=self._dry_run,
)
```

**Contract types required:**
- `SyncMap` — serializable to JSON via Pydantic
- `SyncResult` — return value with sync_map + items_created counter dict + dry_run flag

**Note:** Sync map persistence (writing to `config.sync_path`) is handled by the SDK after the engine returns. This keeps the engine free of file I/O, consistent with the principle that plan loading is also external to the engine.

## Internal Utilities

These are engine-internal, not Contracts:

| Utility | Signature | Purpose |
|---------|-----------|---------|
| `parse_metadata_block` | `(body: str) -> dict[str, str]` | Extract PLAN_ID, ITEM_ID from metadata block in item body |
| `compute_parent_blocked_by` | `(items: list[PlanItem], item_type: PlanItemType) -> set[tuple[str, str]]` | Roll up child deps to parent level |

## Contracts Summary

Complete list of all Contract types the engine requires, organized by domain:

### plan domain

| Type | Fields/Methods Used |
|------|-------------------|
| `Plan` | `.items: list[PlanItem]` |
| `PlanItem` | `.id`, `.type`, `.title`, `.parent_id`, `.sub_item_ids`, `.depends_on`, `.estimate` |
| `PlanItemType` | `EPIC`, `STORY`, `TASK` — used for processing order and `CreateItemInput.item_type` |

### item domain

| Type | Fields/Methods Used |
|------|-------------------|
| `Item` | `.id`, `.key`, `.url`, `.body`, `.set_parent()`, `.add_dependency()` |
| `CreateItemInput` | `.title`, `.body`, `.item_type`, `.labels`, `.size` |
| `UpdateItemInput` | `.title`, `.body`, `.item_type`, `.labels`, `.size` |
| `ItemSearchFilters` | `.labels`, `.body_contains` |

### sync domain

| Type | Fields/Methods Used |
|------|-------------------|
| `SyncEntry` | `.id`, `.key`, `.url`, `.item_type` |
| `SyncMap` | `.plan_id`, `.target`, `.board_url`, `.entries` |
| `SyncResult` | `.sync_map`, `.items_created`, `.dry_run` |
| `to_sync_entry()` | `(Item) -> SyncEntry` |

### config domain

| Type | Fields/Methods Used |
|------|-------------------|
| `PlanPilotConfig` | `.target`, `.board_url`, `.label` |

### provider domain

| Type | Methods Used |
|------|-------------|
| `Provider` | `.search_items()`, `.create_item()`, `.update_item()` |

### renderer domain

| Type | Fields/Methods Used |
|------|-------------------|
| `BodyRenderer` | `.render(PlanItem, RenderContext) -> str` |
| `RenderContext` | `.plan_id`, `.parent_ref`, `.sub_items`, `.dependencies` |

### exceptions

| Type | Used For |
|------|---------|
| `SyncError` | Missing sync map entries, parent mismatches, surfaced partial create failures |

## Changes from v1

| v1 | v2 | Rationale |
|----|-----|-----------|
| Engine calls `load_plan()`, `validate_plan()`, `compute_plan_id()` | SDK handles plan loading and hashing; engine receives `Plan` + `plan_id` | Engine is pure orchestration, no I/O or cross-Core imports |
| Engine calls `renderer.render_epic()`, `render_story()`, `render_task()` | Single `renderer.render(item, context)` | Decouples renderer from entity types |
| Engine knows about `RepoContext`, `ProjectContext`, field resolution | Provider handles all setup in `__aenter__`; engine just calls CRUD | Engine doesn't know about provider internals |
| Engine calls `provider.set_issue_type()`, `add_to_project()`, `set_project_field()` | `Provider.create_item()` handles these as an idempotent multi-step workflow | Simpler engine, provider owns platform-specific setup |
| Engine builds `#123` refs using `issue_number` | Engine uses `SyncEntry.key` (provider-agnostic) | Works for any provider, not just GitHub |
| Relations use `node_id` and `get_issue_relations()` for idempotency | `Item.add_dependency()` and `Item.set_parent()` handle idempotency internally | Moves complexity into provider where it belongs |
