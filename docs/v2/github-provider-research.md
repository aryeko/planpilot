# GitHub Provider — Implementation Design

## Requirements

The v2 `GitHubProvider` needs:

| Operation | API | Notes |
|-----------|-----|-------|
| Fetch repo context | GraphQL | Repo ID, issue types, labels |
| Create label (if missing) | GraphQL | Bootstrap discovery label |
| Create issue | GraphQL | `createIssue` mutation |
| Update issue | GraphQL | `updateIssue` mutation (title/body, additive labels) |
| Update issue type | GraphQL | `updateIssueType` mutation (mode-dependent) |
| Search issues | GraphQL | By label + body text |
| Add label | GraphQL | `addLabelsToLabelable` — no REST needed |
| Add to project | GraphQL | `addProjectV2ItemById` |
| Set project field | GraphQL | `updateProjectV2ItemFieldValue` |
| Fetch project fields | GraphQL | Field IDs, options, iterations |
| Fetch project items | GraphQL | Build/refresh issue->project item map |
| Add sub-issue | GraphQL | `addSubIssue` — confirmed in public schema |
| Add blocked-by | GraphQL | `addBlockedBy` — confirmed in public schema |
| Fetch relations | GraphQL | `parent`, `blockedBy` on Issue type |

**Key finding:** All operations are GraphQL. PlanPilot does not need REST at all.

## Architecture: Two Separated Concerns

### 1. Authentication (Token Resolution)

How we obtain a token is orthogonal to the provider. The provider receives an authenticated token and uses it.

```
auth/
├── base.py            # TokenResolver ABC
├── gh_cli.py          # Shell out to `gh auth token` once
├── env.py             # Read GITHUB_TOKEN env var
└── static.py          # Direct injection (testing, CI, programmatic)
```

```python
class TokenResolver(ABC):
    """Resolves a GitHub API token from some source."""
    @abstractmethod
    async def resolve(self) -> str: ...

class GhCliTokenResolver(TokenResolver):
    """Resolve token via `gh auth token` (single subprocess call)."""
    async def resolve(self) -> str:
        proc = await asyncio.create_subprocess_exec(
            "gh", "auth", "token", stdout=PIPE, stderr=PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            raise AuthenticationError("gh auth failed. Run `gh auth login`.")
        return stdout.decode().strip()

class EnvTokenResolver(TokenResolver):
    """Resolve token from GITHUB_TOKEN environment variable."""
    async def resolve(self) -> str:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise AuthenticationError("GITHUB_TOKEN not set.")
        return token

class StaticTokenResolver(TokenResolver):
    """Directly injected token (testing, CI)."""
    def __init__(self, token: str) -> None:
        self._token = token
    async def resolve(self) -> str:
        return self._token
```

**Resolution happens in the SDK layer** before provider construction:

```python
token = await token_resolver.resolve()
provider = GitHubProvider(target="owner/repo", token=token, ...)
```

**Resolution order** (configurable via `planpilot.json`):

The config file specifies which resolver to use:

```json
{
  "provider": "github",
  "auth": "gh-cli"
}
```

| `auth` value | Resolver | Notes |
|-------------|----------|-------|
| `"gh-cli"` (default) | `GhCliTokenResolver` | Shells out to `gh auth token` once |
| `"env"` | `EnvTokenResolver` | Reads `GITHUB_TOKEN` env var |
| `"token"` | `StaticTokenResolver` | Reads `token` field from config (not recommended for committed files) |

If `auth` is omitted, defaults to `"gh-cli"`.

### 2. Provider Implementation (Typed API Client)

The provider uses a **generated typed GraphQL client** for all API operations. No subprocess per call. httpx connection pooling. Full Pydantic response models.

## Recommended Approach: ariadne-codegen

[ariadne-codegen](https://github.com/mirumee/ariadne-codegen) generates a fully typed async Python client from a GraphQL schema + operation files.

### Why ariadne-codegen

| Criterion | ariadne-codegen |
|-----------|----------------|
| **GraphQL type safety** | Full Pydantic models per operation — every response field is typed |
| **Transport** | httpx with connection pooling and async |
| **Schema validation** | Operations validated against schema at codegen time |
| **Drift detection** | Re-run codegen → mypy catches breakage immediately |
| **Runtime deps** | pydantic + httpx (already in our stack) |
| **Codegen deps** | ariadne-codegen (dev-only, not a runtime dep) |
| **Generated footprint** | Minimal with `include_all_inputs=false`, `include_all_enums=false` |
| **Maintenance** | Update `.graphql` files, re-run codegen. Schema updates are automated |

### Why not the alternatives

| Option | Reason to skip |
|--------|---------------|
| **githubkit** | GraphQL returns raw `dict[str, Any]` — no type safety for our primary API surface. Its strength (typed REST) is irrelevant since PlanPilot is 100% GraphQL |
| **sgqlc** | Python DSL for query construction is less ergonomic than `.graphql` files. Schema-mirror types, not per-operation response types |
| **Hand-written Pydantic models** | Same work as codegen output, but manual, error-prone, and no schema validation |
| **Raw httpx + query strings** | No type safety at all — just `dict[str, Any]` with extra steps |

### Setup

**Schema source:** GitHub's public GraphQL schema at [octokit/graphql-schema](https://github.com/octokit/graphql-schema) (`schema.graphql`).

**Configuration** (`pyproject.toml`):

```toml
[tool.ariadne-codegen]
schema_path = "src/planpilot/providers/github/schema.graphql"
queries_path = "src/planpilot/providers/github/operations/"
target_package_name = "github_gql"
target_package_path = "src/planpilot/providers/github/"
async_client = true
include_all_inputs = false
include_all_enums = false
include_comments = "stable"
```

**Operation files** (`.graphql`) — one per logical operation:

```graphql
# operations/fetch_repo.graphql
query FetchRepo($owner: String!, $name: String!, $label: String!) {
  repository(owner: $owner, name: $name) {
    id
    issueTypes(first: 100) {
      nodes { id name }
      pageInfo { hasNextPage endCursor }
    }
    labels(query: $label, first: 20) {
      nodes { id name }
      pageInfo { hasNextPage endCursor }
    }
  }
}
```

```graphql
# operations/create_issue.graphql
mutation CreateIssue($input: CreateIssueInput!) {
  createIssue(input: $input) {
    issue { id number url }
  }
}
```

```graphql
# operations/add_sub_issue.graphql
mutation AddSubIssue($input: AddSubIssueInput!) {
  addSubIssue(input: $input) {
    issue { id }
    subIssue { id }
  }
}
```

**Generated output** (auto-generated, not hand-written):

```python
# github_gql/client.py (generated)
class Client(AsyncBaseClient):
    async def fetch_repo(self, owner: str, name: str, label: str) -> FetchRepo: ...
    async def create_issue(self, input: CreateIssueInput) -> CreateIssue: ...
    async def add_sub_issue(self, input: AddSubIssueInput) -> AddSubIssue: ...
    # ... typed method per operation

# github_gql/fetch_repo.py (generated)
class FetchRepoRepository(BaseModel):
    id: str
    issue_types: FetchRepoRepositoryIssueTypes
    labels: FetchRepoRepositoryLabels

class FetchRepo(BaseModel):
    repository: FetchRepoRepository | None
```

### Provider wiring

The provider constructs the generated client with a token and delegates all API calls:

```python
class GitHubProvider(Provider):
    def __init__(self, *, target: str, token: str, board_url: str | None, ...) -> None:
        self._target = target
        self._token = token
        self._board_url = board_url
        self._client: Client | None = None

    async def __aenter__(self) -> Provider:
        self._client = Client(
            url="https://api.github.com/graphql",
            headers={"Authorization": f"Bearer {self._token}"},
        )
        # Resolve repo context, project context, field IDs
        await self._resolve_context()
        return self

    async def create_item(self, input: CreateItemInput) -> Item:
        result = await self._retryable(self._client.create_issue,
            input=GqlCreateIssueInput(
                repository_id=self._ctx.repo_id,
                title=input.title,
                body=input.body,
                label_ids=[self._ctx.label_id],
            )
        )
        # result.create_issue.issue is fully typed — .id, .number, .url
        issue = result.create_issue.issue
        # ... idempotent ensure_* steps: type, project item, fields
        return GitHubItem(...)
```

## Operational Hardening Requirements

### Idempotent Multi-Step Create

`create_item()` is not atomic at API level. It must execute retry-safe ensure steps:

1. Create issue
2. Ensure issue type
3. Ensure label assignment
4. Ensure project item (if board configured)
5. Ensure project fields (`size` when present; workflow fields only on create)

On partial failure, provider errors should include enough context for reconciliation:
- `created_item_id`
- `created_item_key`
- `created_item_url`
- `completed_steps`
- `retryable`

Metadata must be present in the body at issue-creation time so discovery can recover from partial setup. If creation happens without metadata due provider/API anomaly, provider should perform a best-effort fallback discovery (`label + title + recent-created window`) and emit a warning.

### Issue Type Mapping and Compatibility

Issue type updates are controlled by provider mode:
- `required` -> missing mapping/capability is a hard failure
- `best-effort` -> missing mapping/capability logs warning and continues
- `disabled` -> no issue type mutation is attempted

Mapping defaults: `EPIC->Epic`, `STORY->Story`, `TASK->Task`; providers may override via config.

### Capability Gating for Relations

Relation mutations (`addSubIssue`, `addBlockedBy`) may be unavailable in some environments. Provider startup should detect capabilities and set flags in context. Relation methods should no-op with warning when unsupported, not fail the whole sync.

Recommended detection mechanism:
- startup probe query against schema/introspection or a dedicated capability query
- cache booleans in provider context (`supports_sub_issues`, `supports_blocked_by`)

### Retry and Rate-Limit Policy

- Use bounded exponential backoff for retryable failures (transport timeouts, 5xx, secondary rate limits).
- Respect `Retry-After` when present.
- Treat schema/validation/auth failures as terminal (no retry).
- Log retry attempts with operation name and attempt count.
- Cap concurrent in-flight GraphQL operations (provider-level semaphore) to reduce secondary rate-limit risk.

Retry classification matrix:

| Failure class | Retry? | Notes |
|---------------|--------|------|
| Network timeout / connection reset | Yes | Exponential backoff |
| HTTP 502/503/504 | Yes | Respect `Retry-After` if present |
| HTTP 429 / secondary rate limit | Yes | Respect `Retry-After`, reduce concurrency |
| GraphQL `errors` with transient classification | Yes | Parse `errors[*].extensions` and message |
| GraphQL schema/validation errors | No | Operation/spec mismatch |
| Authentication/authorization failures | No | Requires config/token fix |

### Pagination Requirements

The provider must paginate through:
- repo issue types
- label lookup queries
- search results
- project item listing (`FetchProjectItems`)
- relation fetches when needed for idempotency checks

Pagination operating rules:
- keep cursor until `hasNextPage == false`
- use bounded page size (for example 50-100 depending on endpoint cost)
- enforce max-page safety budget; fail loudly when exceeded (no silent truncation)
- discovery must fail if pagination truncates results, to avoid duplicate creation

### Project Field Type Handling

`updateProjectV2ItemFieldValue` requires type-specific payloads. Implementation must branch by field kind (single-select, iteration, number) and validate config values before mutation.

## File Structure

```
providers/github/
├── __init__.py
├── provider.py              # GitHubProvider (implements Provider ABC)
├── item.py                  # GitHubItem (implements Item relation methods)
├── models.py                # GitHubProviderContext
├── mapper.py                # Generated types -> domain model mappers
├── schema.graphql           # GitHub's public GraphQL schema (vendored)
├── operations/              # .graphql operation files (source of truth)
│   ├── fetch_repo.graphql
│   ├── create_label.graphql
│   ├── fetch_project.graphql
│   ├── fetch_project_items.graphql
│   ├── search_issues.graphql
│   ├── create_issue.graphql
│   ├── update_issue.graphql
│   ├── add_project_item.graphql
│   ├── update_project_field.graphql
│   ├── add_sub_issue.graphql
│   ├── add_blocked_by.graphql
│   └── fetch_relations.graphql
└── github_gql/              # Generated by ariadne-codegen (gitignored or committed)
    ├── __init__.py
    ├── client.py
    ├── input_types.py
    ├── enums.py
    ├── fetch_repo.py
    ├── create_issue.py
    └── ...
```

### Generated code: commit or gitignore?

| Approach | Trade-off |
|----------|-----------|
| **Commit generated code** | CI doesn't need ariadne-codegen installed. What you see is what runs. Diffs show exactly what changed. |
| **Gitignore + generate in CI** | Cleaner repo. Guaranteed fresh. Requires codegen in CI/dev setup. |

**Recommendation:** Commit the generated code. Add a CI check that re-runs codegen and verifies no diff. This gives both reproducibility and visibility.

## Operations Inventory

Complete list of GraphQL operations PlanPilot needs:

| Operation | Type | GraphQL Operation | Used By |
|-----------|------|-------------------|---------|
| Fetch repo context | Query | `FetchRepo` | `__aenter__` |
| Create label | Mutation | `CreateLabel` | `__aenter__` (if label missing) |
| Fetch project fields | Query | `FetchProject` | `__aenter__` |
| Search issues | Query | `SearchIssues` | `search_items()` |
| Create issue | Mutation | `CreateIssue` | `create_item()` |
| Update issue | Mutation | `UpdateIssue` | `update_item()` |
| Add label | Mutation | `AddLabels` | `create_item()` ensure label assignment |
| Set issue type | Mutation | `UpdateIssueType` | `create_item()` |
| Add to project | Mutation | `AddProjectItem` | `create_item()` |
| Set project field | Mutation | `UpdateProjectField` | `create_item()` |
| Fetch project items | Query | `FetchProjectItems` | `__aenter__` (item map) |
| Add sub-issue | Mutation | `AddSubIssue` | `GitHubItem.set_parent()` |
| Add blocked-by | Mutation | `AddBlockedBy` | `GitHubItem.add_dependency()` |
| Fetch relations | Query | `FetchRelations` | `GitHubItem` (idempotency check) |

**14 operations total.** All confirmed available in the public GitHub GraphQL schema, with relation ops capability-gated at runtime.

## Schema Update Workflow

When GitHub updates their GraphQL schema:

1. Download latest `schema.graphql` from [octokit/graphql-schema](https://github.com/octokit/graphql-schema)
2. Run `ariadne-codegen`
3. If codegen succeeds → schema change is compatible. Commit updated generated code.
4. If codegen fails → our operations reference removed/changed fields. Update `.graphql` files, re-run, fix type errors.
5. Run `poe typecheck` — mypy catches any response field changes in provider code.

This can be automated with a scheduled CI job or Dependabot-like workflow.

## Developer Workflow

**Adding a new GraphQL operation:**

1. Write `.graphql` file in `operations/`
2. Run `ariadne-codegen`
3. Use the generated typed method in provider code
4. mypy validates everything end-to-end

**Modifying an existing operation (e.g. requesting additional fields):**

1. Edit the `.graphql` file
2. Re-run `ariadne-codegen`
3. Generated response models update automatically
4. Compiler/mypy shows you everywhere the new fields are available

## Token Resolver Integration

The factory reads the `auth` setting from config and wires the resolver:

```python
# auth/factory.py
RESOLVERS: dict[str, type[TokenResolver]] = {
    "gh-cli": GhCliTokenResolver,
    "env": EnvTokenResolver,
    "token": StaticTokenResolver,
}

def create_token_resolver(config: PlanPilotConfig) -> TokenResolver:
    """Create a token resolver from config."""
    auth = config.auth or "gh-cli"
    cls = RESOLVERS.get(auth)
    if cls is None:
        raise ConfigError(f"Unknown auth method: {auth!r}")
    if auth == "token":
        return cls(token=config.token)
    return cls()
```

The SDK wires auth and provider together (inside `PlanPilot.from_config(...)`):

```python
# sdk.py (inside sync())
resolver = create_token_resolver(config)
token = await resolver.resolve()
provider = GitHubProvider(target=config.target, token=token, ...)
```

## Summary

| Concern | Solution |
|---------|----------|
| **Auth** | `TokenResolver` ABC — `gh auth token`, `GITHUB_TOKEN`, or direct injection |
| **GraphQL client** | ariadne-codegen — typed async client generated from schema + operations |
| **Transport** | httpx with connection pooling (via ariadne-codegen's default base client) |
| **Type safety** | Full Pydantic models for every response, validated at codegen time |
| **REST** | Not needed — all operations are available via GraphQL |
| **Schema source** | [octokit/graphql-schema](https://github.com/octokit/graphql-schema) (public, auto-updated) |
| **Runtime deps** | pydantic + httpx (already in stack) |
| **Dev deps** | ariadne-codegen (codegen only) |
