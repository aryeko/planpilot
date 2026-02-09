# Engine Module Spec

## Overview

The engine module (`engine/`) orchestrates the sync pipeline. It receives a `Plan`, a `Provider`, and a `BodyRenderer` via dependency injection and runs a multi-phase sync that creates/updates work items in the external system.

The engine is the primary consumer of all Contracts. Every contract type used below is defined in the Contracts layer.

## Dependencies (Contracts only)

| Contract Domain | Types Used |
|----------------|-----------|
| **plan** | `Plan`, `PlanItem` |
| **item** | `Item`, `CreateItemInput`, `UpdateItemInput`, `ItemSearchFilters`, `ItemType` |
| **sync** | `SyncEntry`, `SyncMap`, `SyncResult`, `to_sync_entry()` |
| **config** | `PlanPilotConfig` |
| **provider** | `Provider` ABC |
| **renderer** | `BodyRenderer` ABC, `RenderContext` |
| **exceptions** | `SyncError` |

## SyncEngine Class

```python
class SyncEngine:
    def __init__(
        self,
        provider: Provider,
        renderer: BodyRenderer,
        config: PlanPilotConfig,
    ) -> None: ...

    async def sync(self, plan: Plan) -> SyncResult: ...
```

The engine receives a fully constructed `Provider` (already authenticated via `__aenter__`), a `BodyRenderer`, and config. The `Plan` is passed to `sync()` — the engine does not load plans itself (that's the SDK's job).

### Sync Pipeline

```mermaid
flowchart LR
    Discovery --> Upsert --> Enrich --> Relations --> Result
```

In dry-run mode, only Upsert runs (with placeholder entries, no API calls). Discovery, Enrich, and Relations are skipped.

## Phase 1: Discovery

**Goal:** Find items that already exist in the provider for this plan, so we can skip re-creating them.

**Contract calls:**

```python
filters = ItemSearchFilters(
    labels=[config.label],
    body_contains=f"PLAN_ID: {plan_id}",
)
existing_items: list[Item] = await provider.search_items(filters)
```

**Internal logic:**

The engine parses body markers from each `Item.body` to extract `plan_id`, `epic_id`, `story_id`, `task_id`. Items whose `plan_id` matches are indexed into a lookup dict:

```python
existing_map: dict[str, dict[str, Item]]
# {"epics": {"E1": Item, ...}, "stories": {...}, "tasks": {...}}
```

**Contract types required:**
- `ItemSearchFilters` — needs `labels: list[str]`, `body_contains: str`
- `Item` — needs `id`, `key`, `url`, `body` fields
- `Provider.search_items(ItemSearchFilters) -> list[Item]`

**Internal utilities:**
- `parse_markers(body: str) -> dict[str, str]` — extracts `PLAN_ID`, `EPIC_ID`, etc. from body text. This is an engine-internal utility, not a contract.

## Phase 2: Upsert

**Goal:** For each PlanItem (epic, story, task) in the plan, create it if it doesn't exist.

**Processing order:** Epics first, then stories, then tasks (parent before child so parent refs are available).

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

# 3. Create item
input = CreateItemInput(
    title=plan_item.title,
    body=body,
    item_type=ItemType.EPIC,              # or STORY, TASK
    labels=[config.label],
    size=plan_item.estimate.tshirt,       # if available
)
item: Item = await provider.create_item(input)

# 4. Record in sync map
entry: SyncEntry = to_sync_entry(item)
sync_map.epics[plan_item.id] = entry
```

**Contract types required:**
- `RenderContext` — needs `plan_id: str`, `parent_ref: str`, `sub_items: list[tuple[str, str]]`, `dependencies: dict[str, str]`
- `BodyRenderer.render(PlanItem, RenderContext) -> str`
- `CreateItemInput` — needs `title: str`, `body: str`, `item_type: ItemType`, `labels: list[str]`, `size: str | None`
- `Provider.create_item(CreateItemInput) -> Item`
- `to_sync_entry(Item) -> SyncEntry` — from sync domain
- `SyncMap` — dict-like storage for entries by entity ID

**Dry-run behavior:** In dry-run mode, the engine skips all provider calls and creates placeholder `SyncEntry` objects with `key="dry-run"`, `url="dry-run"`.

## Phase 3: Enrich

**Goal:** Update all bodies with resolved cross-references (now that all items exist and have keys).

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
    UpdateItemInput(body=body),
)
```

**Contract types required:**
- `RenderContext` — same as upsert, but now populated with resolved sub_items and dependencies
- `BodyRenderer.render(PlanItem, RenderContext) -> str`
- `UpdateItemInput` — needs `body: str | None` (only non-None fields applied)
- `Provider.update_item(str, UpdateItemInput) -> Item`

## Phase 4: Relations

**Goal:** Set up parent/child hierarchy and blocked-by dependency links.

**Contract calls:**

```python
# Parent/child: tasks under stories, stories under epics
await item.set_parent(parent_item)

# Blocked-by: direct task deps + roll-ups
await item.add_dependency(blocker_item)
```

**Internal logic:**

1. **Direct task dependencies:** For each task, set `add_dependency` for each task in `depends_on`.
2. **Story roll-up:** If task in story A depends on task in story B, then story A is blocked by story B.
3. **Epic roll-up:** If story in epic A is blocked by story in epic B, then epic A is blocked by epic B.

Roll-up is computed by engine-internal utilities:

```python
def compute_story_blocked_by(items: list[PlanItem]) -> set[tuple[str, str]]: ...
def compute_epic_blocked_by(
    story_blocked: set[tuple[str, str]],
    story_epic_map: dict[str, str],
) -> set[tuple[str, str]]: ...
```

**Contract types required:**
- `Item.set_parent(Item) -> None` — sets parent/child relationship
- `Item.add_dependency(Item) -> None` — sets blocked-by relationship

**Note:** The engine needs `Item` objects (not just `SyncEntry`) for relation calls. During upsert, the engine stores `Item` objects alongside `SyncEntry` entries for use in this phase.

## Phase 5: Result

**Goal:** Persist sync map and return result.

```python
sync_map_json = sync_map.model_dump_json(indent=2)
Path(config.sync_path).write_text(sync_map_json, encoding="utf-8")

return SyncResult(
    sync_map=sync_map,
    epics_created=counters["epics"],
    stories_created=counters["stories"],
    tasks_created=counters["tasks"],
    dry_run=config.dry_run,
)
```

**Contract types required:**
- `SyncMap` — serializable to JSON via Pydantic
- `SyncResult` — return value with sync_map + counters + dry_run flag

## Internal Utilities

These are engine-internal, not Contracts:

| Utility | Signature | Purpose |
|---------|-----------|---------|
| `parse_markers` | `(body: str) -> dict[str, str]` | Extract PLAN_ID, EPIC_ID, etc. from issue body |
| `compute_story_blocked_by` | `(items: list[PlanItem]) -> set[tuple[str, str]]` | Roll up task deps to story level |
| `compute_epic_blocked_by` | `(story_blocked, story_epic_map) -> set[tuple[str, str]]` | Roll up story deps to epic level |

## Contracts Summary

Complete list of all Contract types the engine requires, organized by domain:

### plan domain

| Type | Fields/Methods Used |
|------|-------------------|
| `Plan` | `.epics`, `.stories`, `.tasks` (lists of PlanItem subclasses) |
| `PlanItem` | `.id`, `.title`, `.parent_id`, `.sub_item_ids`, `.depends_on`, `.estimate` |

### item domain

| Type | Fields/Methods Used |
|------|-------------------|
| `Item` | `.id`, `.key`, `.url`, `.body`, `.set_parent()`, `.add_dependency()` |
| `CreateItemInput` | `.title`, `.body`, `.item_type`, `.labels`, `.size` |
| `UpdateItemInput` | `.body` |
| `ItemSearchFilters` | `.labels`, `.body_contains` |
| `ItemType` | `EPIC`, `STORY`, `TASK` |

### sync domain

| Type | Fields/Methods Used |
|------|-------------------|
| `SyncEntry` | `.id`, `.key`, `.url` |
| `SyncMap` | `.plan_id`, `.target`, `.board_url`, `.epics`, `.stories`, `.tasks` |
| `SyncResult` | `.sync_map`, `.epics_created`, `.stories_created`, `.tasks_created`, `.dry_run` |
| `to_sync_entry()` | `(Item) -> SyncEntry` |

### config domain

| Type | Fields/Methods Used |
|------|-------------------|
| `PlanPilotConfig` | `.target`, `.board_url`, `.label`, `.sync_path`, `.dry_run`, `.field_config` |

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
| `SyncError` | Missing sync map entries, parent mismatches |

## Changes from v1

| v1 | v2 | Rationale |
|----|-----|-----------|
| Engine calls `load_plan()`, `validate_plan()`, `compute_plan_id()` | SDK handles plan loading; engine receives `Plan` | Engine is pure orchestration, not I/O |
| Engine calls `renderer.render_epic()`, `render_story()`, `render_task()` | Single `renderer.render(item, context)` | Decouples renderer from entity types |
| Engine knows about `RepoContext`, `ProjectContext`, field resolution | Provider handles all setup in `__aenter__`; engine just calls CRUD | Engine doesn't know about provider internals |
| Engine calls `provider.set_issue_type()`, `add_to_project()`, `set_project_field()` | `Provider.create_item()` handles all of this atomically | Simpler engine, smarter provider |
| Engine builds `#123` refs using `issue_number` | Engine uses `SyncEntry.key` (provider-agnostic) | Works for any provider, not just GitHub |
| Relations use `node_id` and `get_issue_relations()` for idempotency | `Item.add_dependency()` and `Item.set_parent()` handle idempotency internally | Moves complexity into provider where it belongs |
