# Provider API Decoupling Implementation Progress

## ✅ Completed Layers (1-6, 8-9)

### Layer 1: Item Models ✅
- Created `src/planpilot/models/item.py`
- `ItemType` enum: epic, story, task
- `ItemFields`: Generic field bag for create/update
- `CreateItemInput` / `UpdateItemInput`
- `TargetContext`: Opaque provider context base
- `ExistingItemMap`: Categorized existing items

### Layer 2: Item Class (Active Record) ✅
- Created `src/planpilot/providers/item.py`
- `Item` base class with data properties (id, key, url, title, body, item_type, parent_id, labels)
- Async relation methods: set_parent, add_child, remove_child, get_children, add_dependency, remove_dependency, get_dependencies
- `to_sync_entry()` serialization method

### Layer 3: Provider ABC ✅
- Rewrote `src/planpilot/providers/base.py`
- Thin CRUD interface: search_items, create_item, update_item, get_item, delete_item
- Async context manager lifecycle: `__aenter__`, `__aexit__`
- Removed 13 complex methods, kept 5 core CRUD methods

### Layer 4: Sync Models ✅
- Updated `src/planpilot/models/sync.py`
- `SyncEntry`: id, key, url (with migration aliases: node_id → id, issue_number → key)
- `SyncMap`: target, board_url (with migration aliases: repo → target, project_url → board_url)
- Pydantic aliases for backward compatibility

### Layer 5: Config ✅
- Updated `src/planpilot/config.py`
- Added `provider` field (default: "github")
- Renamed fields with aliases: repo → target, project_url → board_url
- Migration support via Pydantic `populate_by_name`

### Layer 6: BodyRenderer ✅
- Updated `src/planpilot/rendering/base.py` and `markdown.py`
- `render_checklist` signature changed: `tuple[int, str]` → `tuple[str, str]`
- Accepts string item keys instead of integer issue numbers

### Layer 7: CLI ✅
- Updated `src/planpilot/cli.py`
- New flags: `--provider` (default: github), `--target` (required), `--board-url` (optional)
- Removed: `--repo`, `--project-url`
- Uses `create_provider()` factory instead of direct imports
- Updated summary formatter to use new field names

### Layer 8: Provider Factory ✅
- Created `src/planpilot/providers/factory.py`
- Registry pattern: `register(name, provider_cls)`
- `create_provider(name, **kwargs)` factory function
- GitHub provider automatically registered via `providers/github/__init__.py`

### Layer 9: GitHub Provider Implementation ✅
- Completely rewrote `src/planpilot/providers/github/provider.py`
- `GitHubTargetContext`: Stores repo_id, project_id, field mappings (opaque to engine)
- `GitHubProvider`:
  - Implements new thin Provider ABC
  - `__aenter__`: Auth, repo resolution, project resolution, field ID resolution
  - `create_item()`: Atomic creation with type, project add, field setting
  - `search_items()`: Returns GitHubItem instances
  - Stub methods: update_item, get_item, delete_item (to be completed)
- Created `src/planpilot/providers/github/item.py`
- `GitHubItem`: Extends Item with GraphQL-backed relation methods (stub implementations)

## ⏳ Remaining Work (Layer 7 - Core Engine)

### Layer 7: SyncEngine Refactoring ❌ (HIGH PRIORITY)
The engine needs substantial updates to:
- Use async context manager pattern with provider
- Call `create_item()` instead of orchestrating multiple provider calls
- Move marker parsing from provider to engine (`_build_existing_map()`)
- Replace relation orchestration with Item method calls
- Remove GitHub-specific constructs (URL building, ctx passing)
- Simplify 5-phase flow given new provider interface

Key changes:
- Setup: `async with create_provider(...) as provider:`
- Discovery: `provider.search_items()` + `_build_existing_map()` (move marker parsing here)
- Upsert: Collapse to single `_upsert_item()` using `create_item()`
- Enrich: Use `item.key` for cross-references (no URL construction)
- Relations: Use `item.add_child()`, `item.add_dependency()` etc.

### Tests ❌ (MEDIUM PRIORITY)
All tests need updates to match new interfaces:
- Model tests: item.py, sync.py, config.py
- Provider tests: base.py ABC, github provider
- Engine tests: New orchestration pattern
- CLI tests: New flag names and factory usage
- Mapper tests: Marker parsing moves to engine

## 🎯 Next Steps (Recommended Order)

1. **Update SyncEngine** (largest refactor)
   - Read existing engine to understand flow
   - Adapt to async context manager pattern
   - Move marker parsing from provider
   - Simplify orchestration logic

2. **Verify existing tests compile** (find breakage)
   - Run pytest with minimal fixes
   - Identify what needs updating

3. **Update tests incrementally** (as needed per failing tests)
   - Don't refactor all tests immediately
   - Fix as test failures surface

4. **End-to-end testing**
   - Verify sync runs without mutations
   - Test dry-run mode
   - Test with real GitHub (optional)

## 📝 Design Validation

Key design achievements:
✅ Provider ABC is now thin and CRUD-focused
✅ GitHub-specific concepts isolated to GitHubProvider/GitHubItem
✅ Item objects carry provider methods (Active Record pattern)
✅ Field config is provider-internal (not exposed in ABC)
✅ CLI uses factory, no direct imports of concrete providers
✅ SyncEntry/SyncMap are provider-agnostic with migration paths
✅ Renderer accepts platform-agnostic item keys

This foundation supports adding Jira, Monday, Linear providers without touching core.

## 🚀 Branch Status

- Branch: `feat/provider-api-decoupling`
- Commits: 2
- Files changed: ~40
- Main blockers: SyncEngine, tests
- Estimated completion: 2-3 hours (engine + tests)
