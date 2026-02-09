# Providers Module Spec

## Overview

The providers module (`providers/`) contains concrete implementations of the `Provider` ABC and a factory for instantiation by name. Each provider adapts an external issue-tracking system (GitHub, Jira, Linear) to the provider contract.

This is a Core (L2) module. It depends only on the Contracts layer.

## Dependencies (Contracts only)

| Contract Domain | Types Used |
|----------------|-----------|
| **item** | `Item`, `CreateItemInput`, `UpdateItemInput`, `ItemSearchFilters` |
| **provider** | `Provider` ABC |
| **config** | `FieldConfig` |
| **exceptions** | `ProviderError`, `ProviderCapabilityError`, `CreateItemPartialFailureError`, `AuthenticationError`, `ProjectURLError` |

No dependency on plan, renderer, sync, or engine.

Third-party/runtime dependencies (for example httpx and generated GraphQL client code) are allowed; "depends only on Contracts" means no imports from other PlanPilot internal layers.

**Module-level base class:**
- `ProviderContext` — Defined in `providers/base.py` (Core layer, not Contracts). A base class that concrete providers subclass to store resolved IDs, field mappings, and other provider-specific state. Opaque to the engine and SDK.

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

### Required Discovery Capabilities

Providers must support Discovery semantics used by the engine:

- `search_items()` must apply `labels` and `body_contains` as a conjunctive filter.
- Search results must be complete up to provider pagination limits (pagination is mandatory).
- If a provider cannot satisfy these semantics, it must fail fast in `__aenter__` with `ProviderCapabilityError` instead of silently degrading.

### Partial Failure Error Contract

`create_item()` is multi-step and may fail after an item already exists remotely. Providers must raise a structured partial-failure exception when that happens:

```python
class CreateItemPartialFailureError(ProviderError):
    created_item_id: str | None
    created_item_key: str | None
    created_item_url: str | None
    completed_steps: tuple[str, ...]
    retryable: bool
```

`completed_steps` uses canonical step names:
- `issue_created`
- `issue_type_set`
- `labels_set`
- `project_item_added`
- `project_fields_set`

Capability gaps must raise:

```python
class ProviderCapabilityError(ProviderError):
    capability: str
```

Example capability names: `discovery_body_contains`, `discovery_label_filter`, `relation_sub_issue`, `relation_blocked_by`.

### Key Design: `create_item()` is Idempotent Multi-Step

In v2, `create_item()` handles everything the v1 engine used to orchestrate across multiple calls, but as a re-runnable workflow (not a single atomic transaction):

| v1 (engine orchestrated) | v2 (provider handles internally) |
|-------------------------|--------------------------------|
| `create_issue()` | Included in `create_item()` |
| `set_issue_type()` | Included in `create_item()` |
| `add_to_project()` | Included in `create_item()` |
| `set_project_field()` (status, priority, iteration, size) | Included in `create_item()` |

The engine just says "create this item" and the provider handles all platform-specific setup. This keeps the engine simple and provider-agnostic.

**Required behavior:**
- Each sub-step must be safe to retry (`ensure_*` semantics).
- Partial failures must raise `CreateItemPartialFailureError` with created item identity + `completed_steps`.
- Re-running sync must converge to one correctly configured item, not duplicates.
- Step ordering must be metadata-safe: issue body metadata is included at issue creation time so crash recovery discovery can find partially configured items.

### Key Design: `Item` is an ABC with Provider-Implemented Relation Methods

`Item` is an abstract base class defined in the Contracts layer. It carries read-only data fields and declares abstract relation methods. Concrete providers return subclasses (e.g. `GitHubItem`) that implement the relation methods using provider-specific APIs. The engine calls these methods through the `Item` ABC without knowing the concrete implementation.

```python
class Item(ABC):
    # Data (read-only)
    id: str
    key: str
    url: str
    title: str
    body: str
    item_type: PlanItemType | None

    # Relation methods (abstract — implemented by provider subclasses)
    @abstractmethod
    async def set_parent(self, parent: Item) -> None: ...
    @abstractmethod
    async def add_dependency(self, blocker: Item) -> None: ...
```

### Key Design: Reconciliation Ownership

Provider `update_item()` applies only plan-authoritative fields:
- `title`, `body`, `item_type`, `labels`, `size`

Provider-authoritative workflow fields (`status`, `priority`, `iteration`) are intentionally not overwritten during reconcile unless future plan schema explicitly models them.

**Label policy:** `labels` is additive (`ensure label present`), not replace-all. Provider must preserve non-PlanPilot labels.

**Project-field policy:** `status`/`priority`/`iteration` from `field_config` are creation defaults. They are not continuously enforced during reconcile in v2.

## Provider Factory

Simple dict-based factory for creating providers by name. No registration mechanism — all known providers are listed in the mapping.

```python
# providers/factory.py
PROVIDERS: dict[str, type[Provider]] = {
    "github": GitHubProvider,
}

def create_provider(
    name: str,
    *,
    target: str,
    token: str,
    board_url: str | None = None,
    label: str = "planpilot",
    field_config: FieldConfig | None = None,
    **kwargs: object,
) -> Provider:
    """Create a provider instance by name.

    Args:
        name: Provider name (must exist in PROVIDERS).
        target: Target designation (e.g. "owner/repo").
        token: Authentication token (resolved externally via TokenResolver).
        board_url: Board URL (optional).
        label: Label name used for create + discovery scoping.
        field_config: Field configuration (optional).

    Returns:
        Provider instance (async context manager).

    Raises:
        ValueError: If name is not in PROVIDERS.
    """
    cls = PROVIDERS.get(name)
    if cls is None:
        raise ValueError(f"Unknown provider: {name!r}")
    return cls(target=target, token=token, board_url=board_url, label=label, field_config=field_config, **kwargs)
```

## GitHub Provider

Concrete implementation of `Provider` for GitHub Issues + Projects v2.

### Architecture

Uses [ariadne-codegen](https://github.com/mirumee/ariadne-codegen) to generate a fully typed async GraphQL client from GitHub's public schema. See `github-provider-research.md` for full rationale and setup details.

```
providers/github/
├── __init__.py         # Package init
├── provider.py         # GitHubProvider (implements Provider ABC)
├── item.py             # GitHubItem (implements Item relation methods)
├── mapper.py           # Generated types -> domain model mappers
├── models.py           # GitHubProviderContext
├── schema.graphql      # GitHub's public GraphQL schema (vendored)
├── operations/         # .graphql operation files (source of truth)
│   ├── fetch_repo.graphql
│   ├── create_issue.graphql
│   └── ...
└── github_gql/         # Generated by ariadne-codegen (committed)
    ├── client.py       # Typed async client (httpx-based)
    ├── input_types.py
    └── ...
```

### GitHubProvider

```python
class GitHubProvider(Provider):
    def __init__(
        self,
        *,
        target: str,              # "owner/repo"
        token: str,               # resolved externally via TokenResolver
        board_url: str | None,
        label: str,
        field_config: FieldConfig | None,
    ) -> None: ...

    async def __aenter__(self) -> Provider:
        """Initialize generated GraphQL client with token, resolve repo context,
        project context, field IDs. Stores resolved state in GitHubProviderContext."""

    async def __aexit__(self, ...):
        """Cleanup."""

    async def search_items(self, filters: ItemSearchFilters) -> list[Item]:
        """Search GitHub issues by label + metadata marker text.
        Must satisfy required discovery capability semantics.
        Returns GitHubItem instances."""

    async def create_item(self, input: CreateItemInput) -> Item:
        """Idempotent multi-step workflow: create issue, set type/labels,
        add to project (if configured), set fields.
        Size/project-field updates are conditional on data and field availability.
        Returns GitHubItem.
        Raises CreateItemPartialFailureError when partially complete."""

    async def update_item(self, item_id: str, input: UpdateItemInput) -> Item:
        """Reconcile plan-authoritative fields for an existing issue.
        Returns GitHubItem."""

    async def get_item(self, item_id: str) -> Item:
        """Fetch single issue by node ID. Returns GitHubItem."""

    async def delete_item(self, item_id: str) -> None:
        """Close/delete issue."""
```

### `__aenter__` — Setup Phase

All provider-specific setup happens here (was scattered across engine phases in v1):

1. **Initialize client** — construct the generated `Client` with the token and `https://api.github.com/graphql` endpoint
2. **Resolve repo context** — fetch repo ID, issue type IDs, resolve or create label
3. **Resolve project context** (if board_url provided) — parse project URL, fetch project fields, resolve field IDs for status/priority/iteration/size
4. **Discovery capability checks** — verify label/body search filters are supported; fail fast with `ProviderCapabilityError` if not
5. **Capability checks** — detect whether relation mutations are available (`addSubIssue`, `addBlockedBy`)
6. **Resolve issue-type policy** — load `issue_type_mode` and `issue_type_map` from `FieldConfig`, validate mapping completeness
7. **Store in `GitHubProviderContext`** — provider-specific context, opaque to the engine

### GitHubItem

Provider-bound `Item` subclass that implements relation methods using the generated GraphQL client.

```python
class GitHubItem(Item):
    _client: Client  # generated ariadne-codegen client
    _ctx: GitHubProviderContext

    async def set_parent(self, parent: Item) -> None:
        """Add sub-issue relationship via GitHub API.
        Idempotent — checks existing relations first.
        No-op with warning if relation capability is unavailable."""

    async def add_dependency(self, blocker: Item) -> None:
        """Add blocked-by relationship via GitHub API.
        Idempotent — checks existing relations first.
        No-op with warning if relation capability is unavailable."""
```

### GitHubProviderContext

Extends `ProviderContext` (from `providers/base.py`) with GitHub-specific resolved state:

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
    supports_sub_issues: bool
    supports_blocked_by: bool
    supports_discovery_filters: bool
    issue_type_mode: str   # "required" | "best-effort" | "disabled"
    issue_type_map: dict[str, str]   # {"EPIC":"Epic","STORY":"Story","TASK":"Task"} by default
```

### Generated GraphQL Client

The `github_gql/client.py` module is auto-generated by ariadne-codegen from the schema and `.graphql` operation files. It provides a typed async method per operation:

```python
# github_gql/client.py (generated — do not edit)
class Client(AsyncBaseClient):
    async def fetch_repo(self, owner: str, name: str, label: str) -> FetchRepo: ...
    async def create_issue(self, input: CreateIssueInput) -> CreateIssue: ...
    async def fetch_project_items(self, project_id: str, cursor: str | None = None) -> FetchProjectItems: ...
    async def add_sub_issue(self, input: AddSubIssueInput) -> AddSubIssue: ...
    # ... one typed method per .graphql operation
```

Transport is httpx with connection pooling and async. All responses are fully typed Pydantic models. See `github-provider-research.md` for setup, codegen config, and schema update workflow.

**Operational requirements:**
- Pagination required for issue types, label resolution, search, and project item scans.
- Retry/backoff required for transient transport and rate-limit failures.
- Provider must classify retryable vs terminal GraphQL errors (including GraphQL `errors` payloads on HTTP 200 responses).

### Mapper

Utility functions for GitHub-specific transformations:

| Function | Purpose |
|----------|---------|
| `parse_project_url(url) -> (org, number)` | Extract org and project number from URL |
| `resolve_option_id(options, name) -> str?` | Case-insensitive option ID lookup |
| `build_parent_map(data) -> dict` | Parse sub-issue API response |
| `build_blocked_by_map(data) -> dict` | Parse blocked-by API response |

**Note:** Metadata parsing (`PLAN_ID`/`ITEM_ID`) is **not** a provider concern in v2. It is an engine-internal utility. The provider's `search_items()` returns raw `Item` objects; the engine parses metadata blocks during Discovery.

### Operations

GraphQL operations are defined as `.graphql` files in `operations/`. ariadne-codegen generates typed methods and response models from these files. See `github-provider-research.md` for the full inventory.

| Operation File | Type | Purpose |
|---------------|------|---------|
| `fetch_repo.graphql` | Query | Fetch repo ID, issue types, label |
| `create_label.graphql` | Mutation | Create label if missing during setup |
| `fetch_project.graphql` | Query | Fetch project fields, options, iterations |
| `fetch_project_items.graphql` | Query | Fetch all project item mappings for reconciliation |
| `search_issues.graphql` | Query | Search issues by label + body text |
| `create_issue.graphql` | Mutation | Create issue |
| `update_issue.graphql` | Mutation | Update issue title/body (and additive labels if needed) |
| `add_project_item.graphql` | Mutation | Add issue to project board |
| `update_project_field.graphql` | Mutation | Set project field value |
| `update_issue_type.graphql` | Mutation | Set issue type (mode-dependent: required/best-effort/disabled) |
| `add_sub_issue.graphql` | Mutation | Create parent/child relationship |
| `add_blocked_by.graphql` | Mutation | Create blocked-by relationship |
| `fetch_relations.graphql` | Query | Batch fetch parents + blocked-by |

## Adding a New Provider

To add a new provider (e.g. Jira):

1. Create `providers/jira/` package
2. Implement `JiraProvider(Provider)` with all abstract methods
3. Implement `JiraItem(Item)` with `set_parent()` and `add_dependency()`
4. Create `JiraClient` for API transport
5. Add to factory mapping in `providers/factory.py`

No changes needed to engine, SDK, CLI, renderers, or any other module.

## Changes from v1

| v1 | v2 | Rationale |
|----|-----|-----------|
| 15+ abstract methods in Provider ABC | 5 CRUD methods + async context manager | Dramatically simpler contract |
| Engine calls `check_auth()`, `get_repo_context()`, `get_project_context()` | Provider handles all setup in `__aenter__` | Engine doesn't know about auth or context resolution |
| Engine calls `set_issue_type()`, `add_to_project()`, `set_project_field()` | `create_item()` handles all as idempotent multi-step workflow | Provider-owned setup with retry-safe convergence |
| Engine calls `add_sub_issue()`, `add_blocked_by()` with raw IDs | `Item.set_parent()`, `Item.add_dependency()` handle idempotency | Relation logic moves to provider |
| Engine calls `get_issue_relations()` for idempotency checks | Item methods handle idempotency internally | Simplifies engine |
| `RepoContext`, `ProjectContext`, `RelationMap` in shared models | GitHub-specific models in `providers/github/models.py` | Provider-specific types stay in provider |
| No factory | Dict-based `create_provider()` factory | Pluggable providers |
| `gh` CLI subprocess per API call | ariadne-codegen + httpx (typed async client) | Type safety, connection pooling, no subprocess overhead |
| Auth embedded in provider (`gh auth status`) | Separated `TokenResolver` — token passed to provider | Auth is orthogonal to API transport |
