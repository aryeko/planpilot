# GitHub Provider Implementation Research

## Context

PlanPilot v2's `GitHubProvider` needs to interact with GitHub's GraphQL API and REST API for:

- **Repo context resolution** — fetch repo ID, issue types, labels
- **Project board operations** — fetch project fields, add items, set field values
- **Issue CRUD** — create, update, search issues
- **Relations** — parent/child sub-issues, blocked-by dependencies
- **Authentication** — verify auth status

The v1 implementation uses a `GhClient` that wraps the `gh` CLI subprocess for all API calls. This document evaluates alternatives.

## Current v1 Approach: `gh` CLI Subprocess

**How it works:** `GhClient` shells out to `gh api graphql` via `asyncio.create_subprocess_exec`, passing queries as `-f query=...` and variables as `-F key=value` flags. Responses are parsed from stdout JSON.

**Strengths:**
- Zero dependency on GitHub HTTP libraries — `gh` handles auth, transport, retries
- `gh` auto-discovers credentials (OAuth token, SSH key, GitHub App)
- Works in CI, local dev, Codespaces — wherever `gh auth login` has been run
- No token management in PlanPilot code at all
- Already proven in v1 production

**Weaknesses:**
- Subprocess overhead per API call (~50-100ms per `gh` invocation)
- No typed responses — everything is `dict[str, Any]` from `json.loads()`
- Error messages from `gh` CLI can be opaque
- Harder to unit test (requires mocking subprocess)
- No connection reuse between calls
- `gh` CLI must be installed on the system

## Option A: githubkit

[githubkit](https://github.com/yanyongyu/githubkit) — Modern, fully-typed Python SDK for GitHub. Auto-generated from GitHub's OpenAPI schema.

### Architecture

- **REST API**: Fully typed methods generated from OpenAPI spec (e.g. `github.rest.repos.get("owner", "repo")` returns `Response[FullRepository]`)
- **GraphQL**: Raw query string approach — `github.graphql(query, variables={...})` returns `dict[str, Any]`
- **Auth**: `TokenAuthStrategy`, `AppAuthStrategy`, `AppInstallationAuthStrategy`, `OAuthAppAuthStrategy`
- **Transport**: Built on `httpx` (sync and async)

### GraphQL Usage Pattern

```python
from githubkit import GitHub

github = GitHub("<token>")

# Async GraphQL
data = await github.async_graphql(
    """
    query($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        id
        issueTypes(first: 100) { nodes { id name } }
      }
    }
    """,
    variables={"owner": "owner", "name": "repo"},
)
repo_id = data["repository"]["id"]
```

### Assessment

| Aspect | Score | Notes |
|--------|-------|-------|
| **REST API typing** | Excellent | Full Pydantic models for all REST endpoints |
| **GraphQL typing** | Poor | Returns raw `dict[str, Any]` — no better than current `gh` CLI approach |
| **Auth flexibility** | Excellent | Token, GitHub App, OAuth — all built in |
| **Async support** | Excellent | Native `httpx` async, no subprocess overhead |
| **Connection reuse** | Good | `httpx` connection pooling |
| **Stability** | Moderate | Not yet stable; minor versions break APIs. Auto-generated from upstream schema changes |
| **Dependencies** | Heavy | Pulls in `httpx`, `hishel`, `pydantic`, `PyJWT`, and auto-generated model code |
| **Maintenance burden** | Low | Auto-generated from GitHub's OpenAPI schema, always up to date |
| **Testing** | Good | Can mock at the `httpx` transport layer |

### Key Insight

**githubkit's strength is REST, not GraphQL.** PlanPilot uses GraphQL almost exclusively (projects v2, issue types, relations, search). For GraphQL, githubkit is just a typed HTTP wrapper that returns raw dicts — essentially the same developer experience as our current `gh` CLI approach, minus the subprocess overhead.

The REST API typing is excellent, but PlanPilot v2 only needs REST for label creation (a single endpoint). The rest is all GraphQL.

## Option B: ariadne-codegen (Generate Typed Client from GitHub Schema)

[ariadne-codegen](https://github.com/mirumee/ariadne-codegen) — Code generator that produces a fully typed Python GraphQL client from a schema + operations.

### Architecture

1. **Download GitHub's GraphQL schema** (publicly available at [octokit/graphql-schema](https://github.com/octokit/graphql-schema))
2. **Write `.graphql` operation files** with all queries/mutations PlanPilot needs
3. **Run `ariadne-codegen`** — generates a typed Python client with:
   - Pydantic models for every response type
   - Async client methods for each operation
   - Full type safety end-to-end

### Generated Code Pattern

```python
# Generated from: queries/fetch_repo.graphql
class FetchRepoRepository(BaseModel):
    id: str
    issue_types: FetchRepoRepositoryIssueTypes
    labels: FetchRepoRepositoryLabels

class FetchRepoResult(BaseModel):
    repository: FetchRepoRepository | None

# Generated client method
class Client(AsyncBaseClient):
    async def fetch_repo(self, owner: str, name: str, label: str) -> FetchRepoResult:
        ...
```

### Assessment

| Aspect | Score | Notes |
|--------|-------|-------|
| **REST API typing** | N/A | GraphQL only — REST would need separate solution |
| **GraphQL typing** | Excellent | Full Pydantic models for all responses, per-operation types |
| **Auth flexibility** | Manual | Must configure httpx transport headers manually |
| **Async support** | Excellent | Generated client is async by default (httpx) |
| **Connection reuse** | Good | httpx connection pooling |
| **Stability** | Good | Schema changes require regeneration, but types catch breakage at codegen time |
| **Dependencies** | Light | Only `pydantic` + `httpx` at runtime (codegen is dev-only) |
| **Maintenance burden** | Medium | Must re-run codegen when schema changes; must update `.graphql` files for new operations |
| **Testing** | Excellent | Generated types make mocking precise and type-safe |

### Key Insight

**ariadne-codegen gives full type safety for GraphQL, which is PlanPilot's primary API surface.** Every query response is a Pydantic model. Every variable is typed. IDE autocompletion works on response fields. Refactors catch type errors at codegen/typecheck time, not at runtime.

The trade-off is maintenance: GitHub's GraphQL schema is large (~70K lines), and regeneration is needed when the schema changes. However, PlanPilot only uses ~12 operations, so the generated code footprint is manageable.

### Concerns

1. **Schema size**: GitHub's full schema is ~70K lines. ariadne-codegen can be configured to only generate models for used operations (`include_all_inputs=false`, `include_all_enums=false`), which shrinks the output significantly.
2. **Preview API features**: GitHub's sub-issues and blocked-by APIs may be in preview. Need to verify schema availability.
3. **Auth story**: No built-in GitHub auth — must configure httpx transport with token header manually. Less convenient than `gh` CLI's auto-discovery.
4. **REST coverage**: Labels API (REST-only) would need a separate small HTTP call. Not a significant issue.

## Option C: `gh` CLI (Enhanced v1 Approach)

Keep the subprocess `gh` CLI wrapper but improve it for v2.

### Enhancements

- **Structured error handling** — Parse `gh` stderr for structured error types
- **Batch query support** — Combine multiple queries into single `gh` invocations where possible
- **Response validation** — Add lightweight Pydantic models for expected response shapes (validation layer on top of raw dicts)
- **Type stubs** — Define TypedDict or Pydantic models for all response types, manually maintained

### Assessment

| Aspect | Score | Notes |
|--------|-------|-------|
| **REST API typing** | N/A | `gh` handles REST via `gh api` |
| **GraphQL typing** | Manual | TypedDicts or response models maintained by hand |
| **Auth flexibility** | Excellent | `gh` handles all auth transparently |
| **Async support** | Good | `asyncio.create_subprocess_exec` |
| **Connection reuse** | Poor | New process per call |
| **Stability** | Excellent | `gh` CLI is very stable; GitHub maintains it |
| **Dependencies** | None | Only stdlib (`asyncio`, `json`) |
| **Maintenance burden** | Low | Just update query strings and response models |
| **Testing** | Moderate | Mock subprocess or `GhClient` class |

## Option D: sgqlc (Simple GraphQL Client)

[sgqlc](https://github.com/profusion/sgqlc) — Schema-based GraphQL client with code generation.

### Architecture

- Generate Python type classes from GitHub's schema introspection
- Build queries programmatically using Python DSL
- Execute via HTTP endpoint

### Assessment

| Aspect | Score | Notes |
|--------|-------|-------|
| **GraphQL typing** | Good | Schema types as Python classes, but less ergonomic than Pydantic models |
| **Auth** | Manual | Must configure HTTP headers |
| **Maturity** | Good | v18, 547 stars, active maintenance |
| **Dependencies** | Light | Minimal dependencies |
| **Developer experience** | Moderate | DSL is less intuitive than raw GraphQL strings; generated code is schema-mirror, not operation-specific |

### Key Insight

sgqlc generates the full schema as Python classes, not per-operation response types. You'd write queries in a Python DSL rather than `.graphql` files. This provides type safety for query construction but not for response shapes. It's a middle ground that's less ergonomic than ariadne-codegen for our use case.

## Option E: Hybrid — `gh` CLI + Thin Response Models

A pragmatic middle ground: keep `gh` CLI for transport and auth, but add Pydantic response models for type safety.

### Architecture

```
providers/github/
├── client.py          # GhClient (gh CLI wrapper, unchanged)
├── models.py          # Pydantic models for GraphQL responses
├── provider.py        # GitHubProvider
├── queries.py         # GraphQL constants (unchanged)
└── mapper.py          # dict -> Pydantic model converters
```

### Pattern

```python
# models.py — response models
class FetchRepoData(BaseModel):
    class Repository(BaseModel):
        id: str
        issue_types: IssueTypeNodes
        labels: LabelNodes
    repository: Repository

# provider.py
raw = await self._client.graphql(FETCH_REPO, variables={...})
data = FetchRepoData.model_validate(raw["data"])
# Now data.repository.id is typed, not data["repository"]["id"]
```

### Assessment

| Aspect | Score | Notes |
|--------|-------|-------|
| **GraphQL typing** | Good | Pydantic response models, manually maintained |
| **Auth** | Excellent | `gh` CLI handles everything |
| **Stability** | Excellent | No dependency on unstable SDKs |
| **Dependencies** | None (extra) | Already use Pydantic |
| **Maintenance** | Medium | Must keep response models in sync with queries |
| **Testing** | Good | Mock `GhClient`, validate against models |

## Comparison Matrix

| Criteria | Weight | gh CLI (C) | gh + Models (E) | githubkit (A) | ariadne-codegen (B) | sgqlc (D) |
|----------|--------|-----------|-----------------|---------------|--------------------|----|
| **GraphQL type safety** | High | Poor | Good | Poor | Excellent | Good |
| **Auth convenience** | High | Excellent | Excellent | Excellent | Poor | Poor |
| **Zero new dependencies** | Medium | Excellent | Excellent | Poor | Moderate | Moderate |
| **Async performance** | Medium | Poor | Poor | Excellent | Excellent | Good |
| **Maintenance burden** | Medium | Low | Medium | Low | Medium | Medium |
| **Developer experience** | Medium | Low | Good | Good | Excellent | Moderate |
| **Testing ergonomics** | Medium | Moderate | Good | Good | Excellent | Moderate |
| **Stability** | High | Excellent | Excellent | Moderate | Good | Good |
| **Migration effort from v1** | Low | None | Low | High | High | High |

## Recommendation

### Primary: Option E — `gh` CLI + Pydantic Response Models

**Recommended for v2 initial implementation.**

**Rationale:**

1. **Auth story is critical.** PlanPilot targets developers who have `gh` installed. The `gh` CLI handles OAuth tokens, SSH keys, GitHub App auth, and Codespaces transparently. No token management code needed. No `GITHUB_TOKEN` environment variable handling. This is a major usability advantage that no pure-HTTP library matches.

2. **Incremental improvement over v1.** The v1 `GhClient` is proven, simple, and works. Adding Pydantic response models on top gives type safety without replacing the transport layer. Migration risk is minimal.

3. **Zero new dependencies.** PlanPilot already depends on Pydantic. No new runtime dependencies are needed. This keeps the package light and avoids version-pinning headaches with auto-generated SDK code.

4. **GraphQL is the primary API.** githubkit's strength (typed REST) doesn't help much here. For GraphQL, it returns raw dicts — no better than `gh` CLI. ariadne-codegen gives full GraphQL typing, but at the cost of a codegen pipeline, auth complexity, and a heavy generated code footprint.

5. **Subprocess overhead is acceptable.** PlanPilot creates 10-100 issues per sync run. At ~80ms per `gh` invocation, that's 0.8–8 seconds of overhead. The bottleneck is GitHub's API rate limit, not subprocess startup time.

6. **Stability.** githubkit warns about breaking changes on minor versions due to upstream schema regeneration. PlanPilot's own response models are controlled and stable.

### Future Consideration: Option B — ariadne-codegen

If PlanPilot evolves to need:
- High-throughput batch operations (100+ items per sync)
- Non-`gh` environments (e.g. web service, serverless)
- GitHub App authentication (server-side)

Then migrating the transport layer to `httpx` with ariadne-codegen for typed GraphQL would be the best upgrade path. The `.graphql` operation files and Pydantic response models from Option E would translate directly into ariadne-codegen inputs, making this a smooth migration.

### Not Recommended

- **githubkit (A)**: Its GraphQL support is no better than raw dicts. Its REST typing is excellent but PlanPilot barely uses REST. The heavy auto-generated dependency is not justified.
- **sgqlc (D)**: The Python DSL for query construction is less ergonomic than raw GraphQL strings for our use case. Schema-mirror types don't give per-operation response types.
- **Pure gh CLI without models (C)**: Works but misses the opportunity to add type safety. Since v2 is a clean break, it's worth adding response models now.

## Implementation Plan (Option E)

### File Structure

```
providers/github/
├── __init__.py
├── provider.py        # GitHubProvider (implements Provider ABC)
├── item.py            # GitHubItem (implements Item relation methods)
├── client.py          # GhClient (async gh CLI wrapper, evolved from v1)
├── models.py          # GitHubProviderContext + Pydantic response models
├── mapper.py          # Raw dict -> domain model converters
└── queries.py         # GraphQL query/mutation constants
```

### Response Model Pattern

Each GraphQL operation gets a corresponding Pydantic response model:

```python
# models.py
class FetchRepoResponse(BaseModel):
    """Response model for FETCH_REPO query."""
    class Repository(BaseModel):
        id: str
        class IssueTypes(BaseModel):
            nodes: list[IssueTypeNode]
        class Labels(BaseModel):
            nodes: list[LabelNode]
        issue_types: IssueTypes = Field(alias="issueTypes")
        labels: Labels
    repository: Repository

class CreateIssueResponse(BaseModel):
    """Response model for CREATE_ISSUE mutation."""
    class CreateIssue(BaseModel):
        class Issue(BaseModel):
            id: str
            number: int
            url: str
        issue: Issue
    create_issue: CreateIssue = Field(alias="createIssue")
```

### GhClient Enhancement

```python
class GhClient:
    async def graphql_typed(
        self,
        query: str,
        response_model: type[T],
        variables: dict[str, Any] | None = None,
    ) -> T:
        """Execute GraphQL and validate response into a Pydantic model."""
        raw = await self.graphql(query, variables)
        return response_model.model_validate(raw["data"])
```

This preserves backward compatibility while adding typed responses.
