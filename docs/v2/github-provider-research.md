# GitHub Provider — Implementation Design

## Requirements

The v2 `GitHubProvider` needs:

| Operation | API | Notes |
|-----------|-----|-------|
| Fetch repo context | GraphQL | Repo ID, issue types, labels |
| Create issue | GraphQL | `createIssue` mutation |
| Update issue | GraphQL | `updateIssue` mutation (body, type) |
| Search issues | GraphQL | By label + body text |
| Add label | GraphQL | `addLabelsToLabelable` — no REST needed |
| Add to project | GraphQL | `addProjectV2ItemById` |
| Set project field | GraphQL | `updateProjectV2ItemFieldValue` |
| Fetch project fields | GraphQL | Field IDs, options, iterations |
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

**Default resolution order** (convenience for CLI users):

1. If `GITHUB_TOKEN` env var is set, use it
2. Otherwise, try `gh auth token`
3. Fail with a clear error message

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
    issueTypes(first: 100) { nodes { id name } }
    labels(query: $label, first: 1) { nodes { id name } }
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
        result = await self._client.create_issue(
            input=GqlCreateIssueInput(
                repository_id=self._ctx.repo_id,
                title=input.title,
                body=input.body,
                label_ids=[self._ctx.label_id],
            )
        )
        # result.create_issue.issue is fully typed — .id, .number, .url
        issue = result.create_issue.issue
        # ... add to project, set fields, etc.
        return GitHubItem(...)
```

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
│   ├── fetch_project.graphql
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
| Fetch project fields | Query | `FetchProject` | `__aenter__` |
| Search issues | Query | `SearchIssues` | `search_items()` |
| Create issue | Mutation | `CreateIssue` | `create_item()` |
| Update issue | Mutation | `UpdateIssue` | `update_item()` |
| Add label | Mutation | `AddLabels` | `create_item()` (if needed) |
| Set issue type | Mutation | `UpdateIssueType` | `create_item()` |
| Add to project | Mutation | `AddProjectItem` | `create_item()` |
| Set project field | Mutation | `UpdateProjectField` | `create_item()` |
| Fetch project items | Query | `FetchProjectItems` | `__aenter__` (item map) |
| Add sub-issue | Mutation | `AddSubIssue` | `GitHubItem.set_parent()` |
| Add blocked-by | Mutation | `AddBlockedBy` | `GitHubItem.add_dependency()` |
| Fetch relations | Query | `FetchRelations` | `GitHubItem` (idempotency check) |

**13 operations total.** All confirmed available in the public GitHub GraphQL schema.

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

The factory wires auth and provider together:

```python
# providers/factory.py
async def create_github_provider(
    *,
    target: str,
    token_resolver: TokenResolver | None = None,
    board_url: str | None = None,
    label: str | None = None,
    field_config: FieldConfig | None = None,
) -> GitHubProvider:
    """Create a GitHubProvider with resolved token."""
    resolver = token_resolver or default_token_resolver()
    token = await resolver.resolve()
    return GitHubProvider(
        target=target,
        token=token,
        board_url=board_url,
        label=label,
        field_config=field_config,
    )

def default_token_resolver() -> TokenResolver:
    """Default: env var first, then gh CLI."""
    if os.environ.get("GITHUB_TOKEN"):
        return EnvTokenResolver()
    return GhCliTokenResolver()
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
