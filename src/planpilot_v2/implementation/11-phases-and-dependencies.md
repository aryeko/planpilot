# Implementation Phases and Dependencies

---

## Dependency Graph

```text
Phase 0: contracts + test-infra  (MUST be first)
    │
    ├── Phase 1a: plan           ─┐
    ├── Phase 1b: auth           ─┤  ALL PARALLEL
    ├── Phase 1c: renderers      ─┤
    ├── Phase 1d: engine         ─┘
    │
    ├── Phase 2: github-provider (can start after Phase 0, overlaps Phase 1)
    │
    ├── Phase 3: sdk             (after ALL Phase 1 + Phase 2 merge into v2)
    │
    └── Phase 4: cli             (after Phase 3)
```

---

## Phase Details

| Phase | Branch | Agent | Depends On | Deliverable |
|-------|--------|-------|------------|-------------|
| 0 | `v2/contracts` | 1 | — | All contract types, ABCs, exceptions, test fixtures, FakeProvider, FakeRenderer |
| 1a | `v2/plan` | 1 | Phase 0 | PlanLoader, PlanValidator, PlanHasher + tests |
| 1b | `v2/auth` | 2 | Phase 0 | TokenResolver + 3 resolvers + factory + tests |
| 1c | `v2/renderers` | 3 | Phase 0 | MarkdownRenderer + factory + tests |
| 1d | `v2/engine` | 4 | Phase 0 | SyncEngine 5-phase + utils + tests |
| 2 | `v2/github-provider` | 5 | Phase 0 | Schema + codegen + GitHubProvider + tests |
| 3 | `v2/sdk` | 1 | All above | PlanPilot + load_config + re-exports + tests |
| 4 | `v2/cli` | 1 | Phase 3 | CLI parser + output + tests |

---

## Merge Order into `v2`

1. `v2/contracts` (+ `v2/test-infra` if separate)
2. `v2/plan`, `v2/auth`, `v2/renderers`, `v2/engine` (any order — they are peers)
3. `v2/github-provider`
4. `v2/sdk`
5. `v2/cli`

---

## New Runtime Dependencies

| Package | Purpose |
|---------|---------|
| `httpx` | Async HTTP client for GitHub GraphQL |

## New Dev Dependencies

| Package | Purpose |
|---------|---------|
| `ariadne-codegen` | Generate typed GraphQL client from schema |

## pyproject.toml Additions

```toml
[tool.poetry.dependencies]
httpx = "^0.28"

[tool.poetry.group.dev.dependencies]
ariadne-codegen = "^0.17"

[tool.ariadne-codegen]
schema_path = "src/planpilot_v2/providers/github/schema.graphql"
queries_path = "src/planpilot_v2/providers/github/operations/"
target_package_name = "github_gql"
target_package_path = "src/planpilot_v2/providers/github/"
async_client = true
include_all_inputs = false
include_all_enums = false
include_comments = "stable"
```

Note: httpx should only be added when the GitHub provider branch starts. For Phases 0-1, no new dependencies are needed.
