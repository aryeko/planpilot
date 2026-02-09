# Providers Module Spec

## Overview

The providers module (`providers/`) contains concrete implementations of the `Provider` ABC and a factory for instantiation by name. Each provider adapts an external issue-tracking system (GitHub, Jira, Linear) to the provider contract.

This is a Core (L2) module. It depends only on the Contracts layer.

## Dependencies (Contracts only)

| Contract Domain | Types Used |
|----------------|-----------|
| **item** | `Item`, `CreateItemInput`, `UpdateItemInput`, `ItemSearchFilters`, `ItemType` |
| **provider** | `Provider` ABC, `ProviderContext` |
| **config** | `FieldConfig` |
| **exceptions** | `ProviderError`, `AuthenticationError`, `ProjectURLError` |

No dependency on plan, renderer, sync, or engine.

## Provider Contract (recap)

Defined in the provider domain of Contracts:

```python
class Provider(ABC):
    async def __aenter__(self) -> Provider: ...
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None: ...
    async def search_items(self, filters: ItemSearchFilters) -> list[Item]: ...
    async def create_item(self, input: CreateItemInput) -> Item: ...
    async def update_item(self, item_id: str, input: UpdateItemInput) -> Item: ...
    async def get_item(self, item_id: str) -> Item: ...
    async def delete_item(self, item_id: str) -> None: ...
```

### Key Design: `create_item()` is Atomic

In v2, `create_item()` handles everything the v1 engine used to orchestrate across multiple calls:

| v1 (engine orchestrated) | v2 (provider handles internally) |
|-------------------------|--------------------------------|
| `create_issue()` | Included in `create_item()` |
| `set_issue_type()` | Included in `create_item()` |
| `add_to_project()` | Included in `create_item()` |
| `set_project_field()` (status, priority, iteration, size) | Included in `create_item()` |

The engine just says "create this item" and the provider handles all platform-specific setup. This keeps the engine simple and provider-agnostic.

### Key Design: `Item` Has Provider-Bound Methods

`Item` is a concrete class with async methods for relations:

```python
class Item:
    # Data (read-only)
    id: str
    key: str
    url: str
    title: str
    body: str
    item_type: ItemType | None

    # Relation methods (provider-bound)
    async def set_parent(self, parent: Item) -> None: ...
    async def add_dependency(self, blocker: Item) -> None: ...
```

Providers return `Item` subclasses that implement these methods using provider-specific APIs. The engine calls them without knowing the implementation.

## ProviderFactory

Registry + factory for creating providers by name.

```python
class ProviderFactory:
    _registry: dict[str, type[Provider]] = {}

    @classmethod
    def register(cls, name: str, provider_cls: type[Provider]) -> None:
        """Register a provider class by name."""

    @classmethod
    def create(
        cls,
        name: str,
        *,
        target: str,
        board_url: str | None = None,
        label: str | None = None,
        field_config: FieldConfig | None = None,
        **kwargs: object,
    ) -> Provider:
        """Create a provider instance by name.

        Args:
            name: Provider name (must be registered).
            target: Target designation (e.g. "owner/repo").
            board_url: Board URL (optional).
            label: Label name (optional).
            field_config: Field configuration (optional).

        Returns:
            Provider instance (async context manager).

        Raises:
            ValueError: If name is not registered.
        """
```

## GitHub Provider

Concrete implementation of `Provider` for GitHub Issues + Projects v2.

### Architecture

```
providers/github/
├── __init__.py         # Self-registration with ProviderFactory
├── provider.py         # GitHubProvider (implements Provider ABC)
├── item.py             # GitHubItem (implements Item relation methods)
├── client.py           # GhClient (async gh CLI wrapper)
├── mapper.py           # Response -> domain model mappers
├── queries.py          # GraphQL query/mutation constants
└── models.py           # GitHub-specific models (GitHubProviderContext, etc.)
```

### GitHubProvider

```python
class GitHubProvider(Provider):
    def __init__(
        self,
        *,
        target: str,              # "owner/repo"
        board_url: str | None,
        label: str | None,
        field_config: FieldConfig | None,
    ) -> None: ...

    async def __aenter__(self) -> Provider:
        """Authenticate, resolve repo context, project context, field IDs.
        Stores resolved state in GitHubProviderContext."""

    async def __aexit__(self, ...):
        """Cleanup."""

    async def search_items(self, filters: ItemSearchFilters) -> list[Item]:
        """Search GitHub issues by label + body text.
        Returns GitHubItem instances."""

    async def create_item(self, input: CreateItemInput) -> Item:
        """Atomically: create issue, set type, add to project, set fields.
        Returns GitHubItem."""

    async def update_item(self, item_id: str, input: UpdateItemInput) -> Item:
        """Update issue title/body. Returns GitHubItem."""

    async def get_item(self, item_id: str) -> Item:
        """Fetch single issue by node ID. Returns GitHubItem."""

    async def delete_item(self, item_id: str) -> None:
        """Close/delete issue."""
```

### `__aenter__` — Setup Phase

All provider-specific setup happens here (was scattered across engine phases in v1):

1. **Authenticate** — verify `gh auth status`
2. **Resolve repo context** — fetch repo ID, issue type IDs, ensure label exists
3. **Resolve project context** (if board_url provided) — parse project URL, fetch project fields, resolve field IDs for status/priority/iteration/size
4. **Store in `GitHubProviderContext`** — provider-specific context, opaque to the engine

### GitHubItem

Provider-bound `Item` subclass that implements relation methods using the `gh` CLI.

```python
class GitHubItem(Item):
    _client: GhClient
    _ctx: GitHubProviderContext

    async def set_parent(self, parent: Item) -> None:
        """Add sub-issue relationship via GitHub API.
        Idempotent — checks existing relations first."""

    async def add_dependency(self, blocker: Item) -> None:
        """Add blocked-by relationship via GitHub API.
        Idempotent — checks existing relations first."""
```

### GitHubProviderContext

Extends `ProviderContext` with GitHub-specific resolved state:

```python
class GitHubProviderContext(ProviderContext):
    repo_id: str
    label_id: str
    issue_type_ids: dict[str, str]       # {"Epic": "...", "Story": "...", "Task": "..."}
    project_id: str | None
    project_item_ids: dict[str, str]     # {issue_node_id: project_item_id}
    status_field: ResolvedField | None
    priority_field: ResolvedField | None
    iteration_field: ResolvedField | None
    size_field_id: str | None
    size_options: list[dict[str, str]]
```

### GhClient

Async wrapper around the `gh` CLI subprocess:

```python
class GhClient:
    async def check_auth(self) -> None: ...
    async def graphql(self, query: str, **variables: object) -> dict: ...
    async def rest(self, method: str, path: str, **kwargs: object) -> dict: ...
```

All GitHub API interactions go through `GhClient`. It handles subprocess execution, JSON parsing, error wrapping (into `ProviderError`), and timeout management.

### Mapper

Utility functions for GitHub-specific transformations:

| Function | Purpose |
|----------|---------|
| `parse_project_url(url) -> (org, number)` | Extract org and project number from URL |
| `resolve_option_id(options, name) -> str?` | Case-insensitive option ID lookup |
| `parse_markers(body) -> dict` | Extract PLAN_ID, ITEM_ID from body (shared with engine) |
| `build_parent_map(data) -> dict` | Parse sub-issue API response |
| `build_blocked_by_map(data) -> dict` | Parse blocked-by API response |

### Queries

GraphQL constants for all GitHub API operations:

| Constant | Operation |
|----------|-----------|
| `CREATE_ISSUE` | Create issue mutation |
| `SEARCH_ISSUES` | Search issues by label + body text |
| `FETCH_REPO` | Fetch repo ID, issue types, label |
| `FETCH_PROJECT` | Fetch project fields, options, iterations |
| `ADD_PROJECT_ITEM` | Add issue to project board |
| `UPDATE_PROJECT_FIELD` | Set project field value |
| `UPDATE_ISSUE_TYPE` | Set issue type |
| `ADD_SUB_ISSUE` | Create parent/child relationship |
| `ADD_BLOCKED_BY` | Create blocked-by relationship |
| `FETCH_ISSUE_RELATIONS` | Batch fetch parents + blocked-by |

### Registration

```python
# providers/github/__init__.py
from planpilot.providers.factory import ProviderFactory
from planpilot.providers.github.provider import GitHubProvider

ProviderFactory.register("github", GitHubProvider)
```

## Adding a New Provider

To add a new provider (e.g. Jira):

1. Create `providers/jira/` package
2. Implement `JiraProvider(Provider)` with all abstract methods
3. Implement `JiraItem(Item)` with `set_parent()` and `add_dependency()`
4. Create `JiraClient` for API transport
5. Register: `ProviderFactory.register("jira", JiraProvider)`

No changes needed to engine, SDK, CLI, renderers, or any other module.

## Changes from v1

| v1 | v2 | Rationale |
|----|-----|-----------|
| 15+ abstract methods in Provider ABC | 6 methods: `search_items`, `create_item`, `update_item`, `get_item`, `delete_item` + context manager | Dramatically simpler contract |
| Engine calls `check_auth()`, `get_repo_context()`, `get_project_context()` | Provider handles all setup in `__aenter__` | Engine doesn't know about auth or context resolution |
| Engine calls `set_issue_type()`, `add_to_project()`, `set_project_field()` | `create_item()` handles all atomically | Single-call item creation |
| Engine calls `add_sub_issue()`, `add_blocked_by()` with raw IDs | `Item.set_parent()`, `Item.add_dependency()` handle idempotency | Relation logic moves to provider |
| Engine calls `get_issue_relations()` for idempotency checks | Item methods handle idempotency internally | Simplifies engine |
| `RepoContext`, `ProjectContext`, `RelationMap` in shared models | GitHub-specific models in `providers/github/models.py` | Provider-specific types stay in provider |
| No factory | `ProviderFactory` with registration | Pluggable providers |
