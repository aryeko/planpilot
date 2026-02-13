# ADR-001: Use ariadne-codegen for GitHub GraphQL Client

**Status:** Accepted
**Date:** 2026-02

## Context

PlanPilot v2's GitHub provider needs a GraphQL client for 22 operations (queries + mutations) plus a shared fragment against GitHub's API. All operations are GraphQL - no REST is needed. The client must be async, typed, and maintainable as GitHub's schema evolves.

## Decision

Use [ariadne-codegen](https://github.com/mirumee/ariadne-codegen) to generate a fully typed async Python client from GitHub's public GraphQL schema + `.graphql` operation files.

### Why ariadne-codegen

| Criterion | ariadne-codegen |
|-----------|----------------|
| **GraphQL type safety** | Full Pydantic models per operation - every response field is typed |
| **Transport** | httpx with connection pooling and async |
| **Schema validation** | Operations validated against schema at codegen time |
| **Drift detection** | Re-run codegen -> mypy catches breakage immediately |
| **Runtime deps** | pydantic + httpx (already in our stack) |
| **Codegen deps** | ariadne-codegen (dev-only, run via pipx - not a runtime dep) |
| **Generated footprint** | Minimal with `include_all_inputs=false`, `include_all_enums=false` |
| **Maintenance** | Update `.graphql` files, re-run codegen |

### Why not the alternatives

| Option | Reason to skip |
|--------|---------------|
| **githubkit** | GraphQL returns raw `dict[str, Any]` - no type safety for our primary API surface. Its strength (typed REST) is irrelevant since PlanPilot is 100% GraphQL |
| **sgqlc** | Python DSL for query construction is less ergonomic than `.graphql` files. Schema-mirror types, not per-operation response types |
| **Hand-written Pydantic models** | Same work as codegen output, but manual, error-prone, and no schema validation |
| **Raw httpx + query strings** | No type safety at all - just `dict[str, Any]` with extra steps |

## Configuration

**Schema source:** GitHub's public GraphQL schema, introspected via `poe gen-schema`.

```toml
# pyproject.toml
[tool.ariadne-codegen]
schema_path = "src/planpilot/core/providers/github/schema.graphql"
queries_path = "src/planpilot/core/providers/github/operations"
target_package_name = "github_gql"
target_package_path = "src/planpilot/core/providers/github"
client_name = "GitHubGraphQLClient"
client_file_name = "client"
async_client = true
convert_to_snake_case = true
include_all_inputs = false
include_all_enums = false
include_comments = "stable"
enable_custom_operations = false
opentelemetry_client = false
plugins = [
    "ariadne_codegen.contrib.extract_operations.ExtractOperationsPlugin",
    "ariadne_codegen.contrib.client_forward_refs.ClientForwardRefsPlugin",
    "ariadne_codegen.contrib.shorter_results.ShorterResultsPlugin",
]
```

### Key configuration choices

| Setting | Value | Why |
|---------|-------|-----|
| `async_client` | `true` | Provider is async-first |
| `convert_to_snake_case` | `true` | Python naming conventions (e.g., `project_v_2_ids` instead of `projectV2Ids`) |
| `include_all_inputs` | `false` | Only generate input types actually used by our operations |
| `include_all_enums` | `false` | Only generate enums referenced by our operations |
| `include_comments` | `"stable"` | Include schema descriptions as docstrings on generated models |
| `ExtractOperationsPlugin` | enabled | Extracts operation strings into a single `operations.py` module |
| `ClientForwardRefsPlugin` | enabled | Generates forward references for lazy imports in the client |
| `ShorterResultsPlugin` | enabled | Client methods return the inner payload type directly for single-field operations |

### Dependency isolation

ariadne-codegen is **not** a Poetry dev dependency. It conflicts with `python-semantic-release` over `click` versions. Instead, it is run via `pipx` in isolated environments:

```toml
[tool.poe.tasks.gen-client]
help = "Generate typed GraphQL client from schema and operations"
shell = "rm -rf src/planpilot/core/providers/github/github_gql && pipx run --spec 'ariadne-codegen>=0.17,<0.18' ariadne-codegen"
```

The `rm -rf` prefix ensures stale files from removed operations are cleaned before regeneration.

## Generated Code: Commit

**Decision:** Commit generated code. Add a CI check that re-runs codegen and verifies no diff.

| Approach | Trade-off |
|----------|-----------|
| **Commit (chosen)** | CI doesn't need ariadne-codegen installed. What you see is what runs. Diffs show exactly what changed |
| **Gitignore + generate in CI** | Cleaner repo. Guaranteed fresh. Requires codegen in CI/dev setup |

## Codegen Scripts

Three `poe` tasks manage schema download and client generation:

| Task | Command | When to use |
|------|---------|-------------|
| `poe gen-schema` | Introspect GitHub GraphQL API | When GitHub updates their schema (rare). Requires `gh` CLI authenticated |
| `poe gen-client` | Generate typed client from schema + operations | After editing any `.graphql` file in `operations/` |
| `poe gen-gql` | Runs `gen-schema` then `gen-client` | Full refresh: new schema + new client |

### `poe gen-schema`

Downloads the latest GitHub GraphQL schema via introspection. Requires the `gh` CLI to be authenticated (`gh auth login`). The token is automatically resolved via `gh auth token`.

```bash
poe gen-schema
```

**Output:** Overwrites `src/planpilot/core/providers/github/schema.graphql`.

**When to run:** Only when you suspect the GitHub schema has changed (new fields, deprecated types). This is rare - GitHub's schema evolves slowly.

### `poe gen-client`

Regenerates the entire `github_gql/` package from the current schema and operations. First deletes the existing generated directory to avoid stale files.

```bash
poe gen-client
```

**Output:** Regenerates `src/planpilot/core/providers/github/github_gql/` with all typed models and the `GitHubGraphQLClient` class.

**When to run:**
- After adding, modifying, or removing any `.graphql` file in `operations/`
- After updating `schema.graphql` (usually after `poe gen-schema`)
- After changing `[tool.ariadne-codegen]` config in `pyproject.toml`

### `poe gen-gql`

Convenience: runs `gen-schema` then `gen-client` in sequence.

```bash
poe gen-gql
```

**When to run:** Full refresh, e.g., when setting up a new development environment or doing a periodic schema update.

## Developer Workflow

### Adding a new GraphQL operation

1. Write a `.graphql` file in `src/planpilot/core/providers/github/operations/`
2. Run `poe gen-client`
3. Use the new typed method on `GitHubGraphQLClient` in provider code
4. Run `poe typecheck` - mypy validates everything end-to-end

### Modifying an existing operation

1. Edit the `.graphql` file (add/remove fields, change variables)
2. Run `poe gen-client`
3. Fix any type errors in provider code (mypy will catch them)
4. Run `poe test` to verify

### Updating the GitHub schema

1. Run `poe gen-schema` (or `poe gen-gql`)
2. If codegen succeeds: schema change is compatible. Commit updated generated code
3. If codegen fails: operations reference removed/changed fields. Update `.graphql` files, re-run
4. Run `poe typecheck` - mypy catches any response field changes in provider code

This can be automated with a scheduled CI job or Dependabot-like workflow.

## Consequences

- **Positive:** Full end-to-end type safety from GraphQL schema to Python code. mypy catches schema drift. No runtime parsing surprises.
- **Positive:** Adding/modifying operations is a 3-step workflow: edit `.graphql`, run codegen, use typed method.
- **Positive:** Provider code is thin (no inline GraphQL strings, no `dict[str, Any]` parsing).
- **Negative:** ariadne-codegen must be available (via pipx) for codegen. Not needed at runtime.
- **Negative:** Schema file must be vendored and periodically updated.
- **Negative:** Generated code in repo adds noise to diffs (mitigated by CI verification check).
