# PlanPilot v2 Architecture

## Design Principles

- **SDK-first** — The CLI is a thin wrapper around a fully-functional SDK. The SDK is the primary interface; programmatic usage is the default, CLI is convenience.

- **Layered dependencies** — Strict downward-only dependencies. Each layer depends only on the layer directly below it. No bypassing, no circular dependencies, no peer imports.

- **Adapter pattern** — Both providers (GitHub, Jira, Linear) and renderers (Markdown, wiki) are pluggable adapters. The core engine knows nothing about concrete implementations.

- **SOLID principles** — Object-oriented design throughout:
  - **Single Responsibility** — Each module has one clear purpose
  - **Open/Closed** — Extend via adapters, not by modifying core
  - **Liskov Substitution** — Any Provider/Renderer implementation works
  - **Interface Segregation** — Clean, focused ABCs
  - **Dependency Inversion** — Engine depends on abstractions, not concretes

- **Async-first** — All I/O operations are async. The SDK and engine are fully async-compatible.

## Layer Architecture

```mermaid
flowchart TB
    subgraph Contracts["Contracts Layer"]
        PlanDomain["plan domain<br/>PlanItem, PlanItemType<br/>Plan"]
        ItemDomain["item domain<br/>Item, CreateItemInput<br/>UpdateItemInput, ItemType"]
        SyncDomain["sync domain<br/>SyncEntry, SyncMap<br/>SyncResult"]
        ConfigDomain["config domain<br/>PlanPilotConfig, FieldConfig"]
        ProviderDomain["provider domain<br/>Provider ABC"]
        RendererDomain["renderer domain<br/>BodyRenderer ABC"]
        Exceptions["exceptions<br/>PlanPilotError hierarchy"]
    end

    subgraph Core["Core Layer"]
        Engine["engine/<br/>SyncEngine<br/>orchestration"]
        PlanCore["plan/<br/>load, validate, hash"]
        Providers["providers/<br/>concrete adapters<br/>+ factory"]
        Renderers["renderers/<br/>concrete renderers<br/>+ factory"]
    end

    subgraph SDK["SDK Layer"]
        PlanPilot["PlanPilot<br/>public API facade"]
    end

    subgraph CLI["CLI Layer"]
        CLIModule["cli.py<br/>arg parsing<br/>output formatting"]
    end

    CLI --> SDK
    SDK --> Engine
    SDK --> PlanCore
    SDK --> Providers
    SDK --> Renderers
    Engine --> ProviderDomain
    Engine --> RendererDomain
    Engine --> PlanDomain
    Engine --> ItemDomain
    Engine --> SyncDomain
    Engine --> ConfigDomain
    PlanCore --> PlanDomain
    Providers --> ProviderDomain
    Providers --> ItemDomain
    Renderers --> RendererDomain
    Renderers --> PlanDomain
    RendererDomain --> PlanDomain
    ProviderDomain --> ItemDomain
```

### Layer Descriptions

#### Contracts

The foundation — pure data types and abstract interfaces. Zero internal dependencies.

Organized into six domains, each with clear responsibilities. Domains may depend on other domains within the same layer (see dependency summary below).

#### 1. **plan** Domain

**Responsibility:** Represents the input structure — the plan entities that users define in JSON files.

**Models:**
- `PlanItemType` — Enum: `EPIC`, `STORY`, `TASK`
- `PlanItem` — Single flat model for all plan entities. The `type` field discriminates between epics, stories, and tasks. All properties live on one class; fields that don't apply to a given type are validated by `PlanValidator`:
  - **Required (all types):** `id: str`, `type: PlanItemType`, `title: str`
  - **Optional / type-dependent:** `goal`, `motivation`, `spec_ref`, `scope`
  - **Hierarchy:** `parent_id`, `sub_item_ids`, `depends_on`
  - **Detail fields:** `assumptions`, `risks`, `estimate`
  - **Story/task fields:** `requirements`, `acceptance_criteria`, `success_metrics`
  - **Task fields:** `verification`
- `PlanItem` sub-models: `Scope`, `SpecRef`, `Estimate`, `Verification` — nested value objects used by `PlanItem` fields
- `Plan` — Container: `items: list[PlanItem]`

**Contracts:** None (pure data models)

**Dependencies:** None

#### 2. **item** Domain

**Responsibility:** Provider-agnostic work item abstraction. Defines what a work item looks like and how to create/update/search items, independent of any specific provider (GitHub, Jira, etc.).

**Models:**
- `CreateItemInput` — Fields required to create a new item
- `UpdateItemInput` — Fields for updating an existing item
- `ItemSearchFilters` — Filters for searching items
- `ItemFields` — Base fields shared by inputs/filters

**Contracts:**
- `Item` ABC — Abstract work item with data fields and abstract relation methods. Concrete providers return subclasses (e.g. `GitHubItem`) that implement the relation methods:
  - `id`, `key`, `url`, `title`, `body`, `item_type` — read-only data fields
  - `set_parent(Item) -> None` — abstract; sets parent/child relationship
  - `add_dependency(Item) -> None` — abstract; sets blocked-by relationship

**Dependencies:**
- Uses `plan` domain: `CreateItemInput.item_type` and `Item.item_type` reference `PlanItemType`

#### 3. **sync** Domain

**Responsibility:** Sync state and results. Tracks what was synced and persists the mapping between plan entities and provider items.

**Models:**
- `SyncEntry` — Mapping entry for a single item (id, key, url)
- `SyncMap` — Full sync map: `plan_id`, `target`, `board_url` (optional), `entries: dict[str, SyncEntry]` (flat, keyed by item ID)
- `SyncResult` — Return value: `sync_map`, `items_created: dict[PlanItemType, int]`, `dry_run`

**Utilities:**
- `to_sync_entry(item: Item) -> SyncEntry` — Converts an Item to a SyncEntry for persistence

**Contracts:** None (pure data models)

**Dependencies:**
- Uses `item` domain: `to_sync_entry()` accepts an `Item`

#### 4. **config** Domain

**Responsibility:** Configuration for sync runs. Loadable from a JSON config file so the SDK and CLI share a single source of truth.

**Models:**
- `PlanPilotConfig` — Top-level configuration, loadable from `planpilot.json`:
  - `provider` — Provider name (e.g. "github")
  - `target` — Target designation (e.g. "owner/repo")
  - `board_url` — Board URL (optional)
  - `plan_paths: PlanPaths` — Paths to plan JSON files
  - `sync_path` — Path to write sync map
  - `label` — Label to apply to all items
  - `field_config` — Project field preferences
  - `dry_run` — Preview mode flag
- `PlanPaths` — Paths configuration for plan input files. Supports multi-file mode (separate epics/stories/tasks files) or single-file mode (all items in one file):
  - `epics: Path | None` — Path to epics JSON file
  - `stories: Path | None` — Path to stories JSON file
  - `tasks: Path | None` — Path to tasks JSON file
  - `unified: Path | None` — Path to single combined plan file
- `FieldConfig` — Project field preferences (status, priority, iteration, size field)

**Contracts:** None (pure data models)

**Dependencies:** None

#### 5. **provider** Domain

**Responsibility:** Contract for external system adapters. Defines what any provider (GitHub, Jira, Linear) must be able to do.

**Contracts:**
- `Provider` ABC — Abstract base class defining the provider interface:
  - `__aenter__()` / `__aexit__()` — Async context manager lifecycle
  - `search_items(ItemSearchFilters) -> list[Item]` — Search for items
  - `create_item(CreateItemInput) -> Item` — Create a new item
  - `update_item(str, UpdateItemInput) -> Item` — Update an existing item
  - `get_item(str) -> Item` — Fetch a single item
  - `delete_item(str)` — Delete an item

**Dependencies:**
- Depends on `item` domain: Uses `CreateItemInput`, `Item`, `UpdateItemInput`, `ItemSearchFilters` in method signatures

**Note:** `ProviderContext` is **not** part of the Contracts layer. It is a base class defined in the Core providers module (`providers/base.py`) that concrete providers subclass to store resolved IDs, field mappings, and other provider-specific state (e.g. `GitHubProviderContext`). It is opaque to the engine and SDK.

#### 6. **renderer** Domain

**Responsibility:** Contract for body formatting. Defines how issue/body content should be rendered in different markup formats. Uses a single unified method that renders any `PlanItem` — the renderer inspects which fields are present and skips empty ones.

**Models:**
- `RenderContext` — Resolved cross-references the engine computed for rendering:
  - `plan_id` — Deterministic plan hash for the marker comment
  - `parent_ref` — Human-readable reference to parent item (e.g. "#42")
  - `sub_items` — List of (key, title) tuples for child items
  - `dependencies` — Dict of {dep_id: issue_ref} for blocked-by links

**Contracts:**
- `BodyRenderer` ABC — Single-method contract for body rendering:
  - `render(item: PlanItem, context: RenderContext) -> str` — Render body for any plan item

**Design:** The renderer does not need to know the item's type. It renders a `PlanItem` and its `RenderContext`. Fields that are empty/None are skipped. This fully decouples the renderer from specific plan entity types.

**Dependencies:**
- Depends on `plan` domain: Uses `PlanItem` in method signature

### Contract Dependencies Summary

```
plan domain          (no dependencies)
    ↑
item domain          (depends on plan — uses PlanItemType)
    ↑
renderer domain      (depends on plan — uses PlanItem)

provider domain      (depends on item — uses Item, inputs)

sync domain          (depends on item — to_sync_entry conversion)

config domain        (no dependencies)
```

**Key points:**
- `plan` and `config` are independent foundations with no dependencies
- `item` domain depends on `plan` (uses `PlanItemType` enum for `Item.item_type` and `CreateItemInput.item_type`)
- `renderer` domain depends on `plan` (uses `PlanItem` in method signature)
- `provider` domain depends on `item` (uses input/output types in method signatures)
- `sync` domain depends on `item` (for `to_sync_entry()` conversion)

#### Core

Four peer modules that contain all business logic. Each depends only on Contracts, never on each other.

**Modules:**

1. **`engine/`** — Sync orchestration
   - `SyncEngine` class — orchestrates the 5-phase sync pipeline
   - `discovery.py` — parse body markers, build existing item maps
   - `relations.py` — compute blocked-by roll-ups (story -> epic)

2. **`plan/`** — Plan file operations
   - `loader.py` — load JSON files into `Plan` objects
   - `validator.py` — validate referential integrity
   - `hasher.py` — compute deterministic plan ID

3. **`providers/`** — Concrete provider adapters
   - `github/` — GitHub implementation
   - `factory.py` — Provider registry and factory

4. **`renderers/`** — Concrete renderer implementations
   - `markdown.py` — Markdown renderer (GitHub-flavored)
   - `factory.py` — Renderer registry and factory

**Rules:**
- Each module depends only on Contracts
- No imports between Core modules
- Engine receives Provider and Renderer via dependency injection
- Factories are Core utilities, not SDK concerns

#### SDK

The public API surface. Wires Core modules together.

**Contents:**
- `PlanPilot` class — main facade
- Exposes provider/renderer factories as convenience functions
- Handles plan loading, dependency injection, engine construction
- Handles sync map persistence to disk after engine returns `SyncResult`

**Rules:**
- Depends on Core modules only
- No business logic — pure orchestration and wiring
- Public API is stable and well-documented

#### CLI

Thin shell wrapper. Depends only on SDK.

**Contents:**
- `cli.py` — argparse setup, output formatting
- Calls SDK with parsed arguments

**Rules:**
- Imports only from the SDK's public API surface. The SDK re-exports any Contracts types needed by callers (e.g. `SyncResult`, `PlanPilotConfig`, `PlanItemType`)
- Does not import Core modules or Contracts directly
- Could be deleted and SDK still works

## Dependency Rules

| Layer | Can Import From | Cannot Import From |
|-------|----------------|-------------------|
| **Contracts** | Other Contract domains (downward only), stdlib, third-party | Core, SDK, CLI |
| **Core** | Contracts only | Other Core modules, SDK, CLI |
| **SDK** | Core, Contracts (re-exports selected types publicly) | CLI |
| **CLI** | SDK public API (which re-exports selected Contracts types) | Core, Contracts directly |

Strict one-level-down. The SDK re-exports Contracts types (e.g. `SyncResult`, `PlanPilotConfig`, `PlanItemType`) so that CLI and external callers access them through the SDK without importing Contracts directly.

## Module Responsibilities

| Module | Responsibility | Layer |
|--------|---------------|-------|
| `plan` domain | Plan entity types: PlanItem, PlanItemType, Plan | Contracts |
| `item` domain | Provider-agnostic work items: Item, CreateItemInput, UpdateItemInput | Contracts |
| `sync` domain | Sync state: SyncEntry, SyncMap, SyncResult, to_sync_entry() | Contracts |
| `config` domain | Configuration: PlanPilotConfig, FieldConfig | Contracts |
| `provider` domain | Provider ABC (adapter contract for external systems) | Contracts |
| `renderer` domain | BodyRenderer ABC (body formatting contract) | Contracts |
| `exceptions` | Exception hierarchy: PlanPilotError, SyncError, ProviderError | Contracts |
| `engine/` | Sync orchestration (5-phase pipeline) | Core |
| `plan/` | Load, validate, hash plan files | Core |
| `providers/` | Concrete provider implementations + factory | Core |
| `renderers/` | Concrete renderer implementations + factory | Core |
| `sdk.py` | Public API facade, dependency wiring | SDK |
| `cli.py` | Arg parsing, output formatting | CLI |

## UML Class Diagram

```mermaid
classDiagram
    class PlanItemType {
        <<enum>>
        EPIC
        STORY
        TASK
    }

    class PlanItem {
        +str id
        +PlanItemType type
        +str title
        +str? goal
        +str? motivation
        +str? parent_id
        +list~str~ sub_item_ids
        +list~str~ depends_on
        +list~str~ requirements
        +list~str~ acceptance_criteria
        +list~str~ success_metrics
        +list~str~ assumptions
        +list~str~ risks
        +Estimate? estimate
        +Verification? verification
        +SpecRef? spec_ref
        +Scope? scope
    }

    class Plan {
        +list~PlanItem~ items
    }

    class Item {
        <<abstract>>
        +str id
        +str key
        +str url
        +str title
        +str body
        +PlanItemType item_type
        +set_parent(Item)*
        +add_dependency(Item)*
    }

    class SyncResult {
        +SyncMap sync_map
        +dict items_created
        +bool dry_run
    }

    class Provider {
        <<abstract>>
        +__aenter__() Provider
        +__aexit__()
        +search_items(ItemSearchFilters) list~Item~
        +create_item(CreateItemInput) Item
        +update_item(str, UpdateItemInput) Item
        +get_item(str) Item
        +delete_item(str)
    }

    class RenderContext {
        +str plan_id
        +str parent_ref
        +list~tuple~ sub_items
        +dict dependencies
    }

    class BodyRenderer {
        <<abstract>>
        +render(PlanItem, RenderContext) str
    }

    class SyncEngine {
        -Provider provider
        -BodyRenderer renderer
        -PlanPilotConfig config
        +sync(Plan) SyncResult
    }

    class PlanLoader {
        +load(paths) Plan
    }

    class PlanValidator {
        +validate(Plan)
    }

    class PlanHasher {
        +compute_plan_id(Plan) str
    }

    class ProviderFactory {
        +register(str, type~Provider~)
        +create_provider(str) Provider
    }

    class RendererFactory {
        +register(str, type~BodyRenderer~)
        +create_renderer(str) BodyRenderer
    }

    class PlanPilot {
        -Provider provider
        -BodyRenderer renderer
        -PlanPilotConfig config
        +sync(plan: Plan | None) SyncResult
    }

    PlanItem --> PlanItemType : has type
    Plan --> PlanItem : contains
    Item --> PlanItemType : has item_type
    SyncEngine --> Provider : uses
    SyncEngine --> BodyRenderer : uses
    SyncEngine --> Plan : processes
    SyncEngine --> Item : works with
    SyncEngine --> SyncResult : returns
    PlanLoader --> Plan : creates
    PlanValidator --> Plan : validates
    PlanHasher --> Plan : hashes
    PlanPilot --> SyncEngine : constructs
    PlanPilot --> Provider : injects
    PlanPilot --> BodyRenderer : injects
    ProviderFactory --> Provider : creates
    RendererFactory --> BodyRenderer : creates
```

## Data Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant SDK as PlanPilot
    participant Engine as SyncEngine
    participant Item as Item
    participant Provider as Provider ABC
    participant Renderer as BodyRenderer

    User->>CLI: planpilot sync --config planpilot.json --apply
    CLI->>SDK: PlanPilot(provider, renderer, config)
    CLI->>SDK: sync()
    SDK->>SDK: load_plan(config.plan_paths)
    SDK->>Provider: __aenter__()
    Provider-->>SDK: authenticated provider

    SDK->>Engine: SyncEngine(provider, renderer, config)
    SDK->>Engine: sync(plan)

    Engine->>Provider: search_items(filters)
    Provider-->>Engine: list[Item]

    loop For each PlanItem
        Engine->>Renderer: render(item, RenderContext)
        Renderer-->>Engine: body string
        Engine->>Provider: create_item(CreateItemInput)
        Provider-->>Engine: Item (with provider injected)
    end

    Engine->>Renderer: render(item, RenderContext with cross-refs)
    Renderer-->>Engine: updated body strings
    Engine->>Provider: update_item(id, UpdateItemInput)

    Engine->>Item: set_parent(parent)
    Item->>Provider: internal relation API call
    Engine->>Item: add_dependency(blocker)
    Item->>Provider: internal relation API call

    Engine-->>SDK: SyncResult
    SDK->>SDK: persist sync map to disk
    SDK->>Provider: __aexit__()
    SDK-->>CLI: SyncResult
    CLI-->>User: formatted output
```

## Public API Surface

### Programmatic Usage

```python
from planpilot import PlanPilot, PlanItemType, create_provider, create_renderer, load_config

# Load config from file
config = load_config("planpilot.json")

# Construct provider and renderer (by name, via factories)
provider = create_provider(config.provider, target=config.target)
renderer = create_renderer("markdown")

# Create SDK instance and sync (loads plan from config.plan_paths)
# Provider lifecycle (__aenter__/__aexit__) is managed internally by sync()
pp = PlanPilot(provider=provider, renderer=renderer, config=config)
result = await pp.sync()

# Or pass a Plan directly for programmatic use
plan = load_plan("epics.json", "stories.json", "tasks.json")
result = await pp.sync(plan)

# Access results
print(f"Created {result.items_created[PlanItemType.EPIC]} epics")
print(f"Sync map: {result.sync_map.model_dump_json()}")
```

**Provider lifecycle:** The `PlanPilot.sync()` method manages the provider's async context manager internally. The caller does **not** need to enter the provider context — `sync()` calls `__aenter__` before engine execution and `__aexit__` after completion (or on error). This keeps the public API simple and ensures proper cleanup.

### CLI Usage

```bash
# Config-file driven (recommended)
planpilot sync --config planpilot.json --apply

# Override individual settings
planpilot sync --config planpilot.json --apply --dry-run
```

Example `planpilot.json`:

```json
{
  "provider": "github",
  "target": "owner/repo",
  "board_url": "https://github.com/orgs/owner/projects/1",
  "plan_paths": {
    "epics": "epics.json",
    "stories": "stories.json",
    "tasks": "tasks.json"
  },
  "sync_path": "sync-map.json",
  "label": "planpilot",
  "field_config": {
    "status": "Backlog",
    "priority": "P1",
    "iteration": "active",
    "size_field": "Size",
    "size_from_tshirt": true
  }
}
```

## Adapter Extension Guide

### Adding a New Provider

1. **Implement the Provider ABC:**

```python
# providers/jira/provider.py
from planpilot.contracts.provider import Provider
from planpilot.contracts.item import Item, CreateItemInput, UpdateItemInput, ItemSearchFilters

class JiraProvider(Provider):
    async def __aenter__(self) -> Provider:
        # Initialize Jira client, authenticate
        return self
    
    async def __aexit__(self, ...):
        # Cleanup
    
    async def search_items(self, filters: ItemSearchFilters) -> list[Item]:
        # Map filters to JQL, execute query, return Items
        ...
    
    async def create_item(self, input: CreateItemInput) -> Item:
        # Create Jira issue, map to Item
        ...
    
    # ... implement all abstract methods
```

2. **Register with factory:**

```python
# providers/jira/__init__.py
from planpilot.providers.factory import register
from planpilot.providers.jira.provider import JiraProvider

register("jira", JiraProvider)
```

3. **Use it:**

```python
provider = create_provider("jira", ...)
pp = PlanPilot(provider=provider, ...)
```

**No changes needed to:** Engine, SDK, CLI, or any other Core modules. Users set `"provider": "jira"` in config.

### Adding a New Renderer

1. **Implement the Renderer Protocol:**

```python
# renderers/wiki/renderer.py
from planpilot.contracts.renderer import BodyRenderer, RenderContext
from planpilot.contracts.plan import PlanItem

class WikiRenderer(BodyRenderer):
    def render(self, item: PlanItem, context: RenderContext) -> str:
        # Render in Jira/wiki format
        lines = [f"h1. {item.title}"]
        if item.goal:
            lines.append(f"\n{item.goal}")
        if context.sub_items:
            lines.append("\nh2. Sub-items")
            for key, title in context.sub_items:
                lines.append(f"* [{key}] {title}")
        # ... skip empty fields automatically
        return "\n".join(lines)
```

2. **Register with factory:**

```python
# renderers/wiki/__init__.py
from planpilot.renderers.factory import register
from planpilot.renderers.wiki.renderer import WikiRenderer

register("wiki", WikiRenderer)
```

3. **Use it:**

```python
renderer = create_renderer("wiki")
pp = PlanPilot(provider=provider, renderer=renderer, ...)
```

**No changes needed to:** Engine, SDK, or any other Core modules.

## Key Architectural Decisions

### Contracts as domain-organized vocabulary

Contracts are not a single `models/` bucket. They are organized into six focused domains (plan, item, sync, config, provider, renderer), each with clear responsibility and minimal cross-domain dependencies. This makes it obvious where a new type belongs and prevents the "models/ junk drawer" anti-pattern.

### Provider and Renderer ABCs live in Contracts, not Core

The interfaces define **what the system needs** from external adapters. They are part of the domain vocabulary alongside `Item` and `Plan`. Core contains only **how** — concrete implementations and factories.

### Engine and Providers are Core peers

The engine doesn't know any concrete provider exists. It receives a `Provider` (the ABC) and calls its methods. Concrete adapters implement `Provider` but don't know the engine exists. They communicate only through Contracts. This is dependency inversion.

### SDK is the composition root

The SDK is the only place that sees all Core modules and wires them together. Core modules never import each other — they are assembled by the SDK. This keeps coupling minimal and each Core module independently testable.

### CLI depends only on SDK

The CLI is pure I/O — argument parsing and output formatting. It never reaches into Core or Contracts directly — it imports only from the SDK's public API surface (which re-exports selected Contracts types like `SyncResult` and `PlanItemType`). The CLI could be replaced with a web UI or a script and the SDK would work unchanged.

## Migration and Operational Notes

### Sync map compatibility

v2 is a major version — sync maps are not backward-compatible with v1. v1 sync maps should be discarded. On first v2 run, the Discovery phase re-detects previously created issues via body markers and rebuilds the sync map in v2 format. No issues are duplicated.

### Partial failure recovery

The Discovery phase re-detects previously created items via body markers (`PLAN_ID`/`ITEM_ID` embedded in issue bodies). If a sync crashes mid-upsert, re-running will find already-created items during Discovery and skip them, continuing from where it left off. This makes the sync pipeline idempotent and crash-safe.

### Concurrency

Provider implementations are not required to support concurrent calls. The engine processes items sequentially (epics, then stories, then tasks). Future versions may introduce opt-in concurrency for providers that support it.
