# ADR-001: Use ariadne-codegen for GitHub GraphQL Client

**Status:** Accepted
**Date:** 2026-02

## Context

PlanPilot v2's GitHub provider needs a GraphQL client for 14 operations (queries + mutations) against GitHub's API. All operations are GraphQL — no REST is needed. The client must be async, typed, and maintainable as GitHub's schema evolves.

## Decision

Use [ariadne-codegen](https://github.com/mirumee/ariadne-codegen) to generate a fully typed async Python client from GitHub's public GraphQL schema + `.graphql` operation files.

### Why ariadne-codegen

| Criterion | ariadne-codegen |
|-----------|----------------|
| **GraphQL type safety** | Full Pydantic models per operation — every response field is typed |
| **Transport** | httpx with connection pooling and async |
| **Schema validation** | Operations validated against schema at codegen time |
| **Drift detection** | Re-run codegen -> mypy catches breakage immediately |
| **Runtime deps** | pydantic + httpx (already in our stack) |
| **Codegen deps** | ariadne-codegen (dev-only, not a runtime dep) |
| **Generated footprint** | Minimal with `include_all_inputs=false`, `include_all_enums=false` |
| **Maintenance** | Update `.graphql` files, re-run codegen |

### Why not the alternatives

| Option | Reason to skip |
|--------|---------------|
| **githubkit** | GraphQL returns raw `dict[str, Any]` — no type safety for our primary API surface. Its strength (typed REST) is irrelevant since PlanPilot is 100% GraphQL |
| **sgqlc** | Python DSL for query construction is less ergonomic than `.graphql` files. Schema-mirror types, not per-operation response types |
| **Hand-written Pydantic models** | Same work as codegen output, but manual, error-prone, and no schema validation |
| **Raw httpx + query strings** | No type safety at all — just `dict[str, Any]` with extra steps |

## Configuration

**Schema source:** GitHub's public GraphQL schema at [octokit/graphql-schema](https://github.com/octokit/graphql-schema).

```toml
# pyproject.toml
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

## Generated Code: Commit

**Decision:** Commit generated code. Add a CI check that re-runs codegen and verifies no diff.

| Approach | Trade-off |
|----------|-----------|
| **Commit (chosen)** | CI doesn't need ariadne-codegen installed. What you see is what runs. Diffs show exactly what changed |
| **Gitignore + generate in CI** | Cleaner repo. Guaranteed fresh. Requires codegen in CI/dev setup |

## Schema Update Workflow

When GitHub updates their GraphQL schema:

1. Download latest `schema.graphql` from [octokit/graphql-schema](https://github.com/octokit/graphql-schema)
2. Run `ariadne-codegen`
3. If codegen succeeds -> schema change is compatible. Commit updated generated code
4. If codegen fails -> our operations reference removed/changed fields. Update `.graphql` files, re-run, fix type errors
5. Run `poe typecheck` — mypy catches any response field changes in provider code

This can be automated with a scheduled CI job or Dependabot-like workflow.

## Consequences

- **Positive:** Full end-to-end type safety from GraphQL schema to Python code. mypy catches schema drift. No runtime parsing surprises.
- **Positive:** Adding/modifying operations is a 3-step workflow: edit `.graphql`, run codegen, use typed method.
- **Negative:** Dev dependency on ariadne-codegen. Schema file must be vendored and periodically updated.
- **Negative:** Generated code in repo adds noise to diffs (mitigated by CI verification check).
