# Overview

> Read this first before working on any v2 module.

## Architecture (4 layers, strict downward-only dependencies)

| Layer | Contents | Can Import From |
|-------|----------|-----------------|
| **Contracts (L1)** | Pure data types, ABCs, exceptions | Other Contract domains (downward only), stdlib, third-party |
| **Core (L2)** | engine, plan, auth, renderers, providers | Contracts only. **Never** other Core modules |
| **SDK (L3)** | `PlanPilot` class — composition root | Core + Contracts |
| **CLI (L4)** | Thin arg-parsing shell | SDK public API only |

**Core modules are peers.** They never import each other. The SDK is the only place that wires them together.

## Design Principles

- **SDK-first** — CLI is a thin wrapper; programmatic usage is default
- **Adapter pattern** — Providers and renderers are pluggable via ABCs
- **Async-first** — All I/O operations are async
- **SOLID** — SRP, OCP via adapters, LSP for Provider/Renderer, ISP via focused ABCs, DI throughout

## Locked Decisions

- Discovery is provider-search-first using metadata marker query (`PLAN_ID:<plan_id>`)
- All renderers emit a shared plain-text metadata block (`PLANPILOT_META_V1` ... `END_PLANPILOT_META`)
- Discovery uses provider-native search APIs with partitioning as needed and fail-fast on truncation/capability limits
- Reconciliation ownership is hybrid:
  - Plan-authoritative: title/body/type/label/size/relations
  - Provider-authoritative: status/priority/iteration after creation
- Exit codes are differentiated (`0`, `2`, `3`, `4`, `5`, `1`)
- SDK is the composition root via `PlanPilot.from_config(...)`
- Dry-run uses a `DryRunProvider` (no auth/network calls, no provider mutations)
- Dry-run sync maps are persisted to `<sync_path>.dry-run`
- Engine owns dispatch concurrency (`max_concurrent`); provider owns per-call retries and rate-limit coordination

## Known Limitations

- Engine processes type levels sequentially (epics -> stories -> tasks); within each level, operations are concurrent up to `max_concurrent`
- Workflow board fields (`status`, `priority`, `iteration`) are provider-authoritative after create
- Relation mutations are capability-gated and produce explicit errors when unsupported
- CLI text summary is human-oriented, not a stable machine interface
- In `validation_mode=partial`, unresolved parent/dependency references are omitted from rendered context and relations for that run

---

## Code Placement

This document now reflects the post-cutover package layout.

| What | Location |
|------|----------|
| Runtime source | `src/planpilot/` |
| Tests | `tests/` |
| Design docs | `src/planpilot/docs/` |

**Import style during development:**

```python
from planpilot.contracts.plan import PlanItem, PlanItemType, Plan
from planpilot.contracts.provider import Provider
from planpilot.engine.engine import SyncEngine
```

**Cutover status:** complete. Legacy v1 paths have been removed and canonicalized to `src/planpilot/` and `tests/`.

---

## Full Package Structure

### Source (`src/planpilot/`)

```text
src/planpilot/
├── __init__.py                         # Re-exports (SDK public API surface)
├── __main__.py                         # python -m planpilot support
├── py.typed                            # PEP 561 marker
│
├── contracts/                          # L1 — Pure types + ABCs
│   ├── __init__.py                     # Re-exports all contract types
│   ├── plan.py                         # PlanItemType, PlanItem, Plan, Scope, SpecRef, Estimate, Verification
│   ├── item.py                         # Item ABC, CreateItemInput, UpdateItemInput, ItemSearchFilters
│   ├── sync.py                         # SyncEntry, SyncMap, SyncResult, to_sync_entry()
│   ├── config.py                       # PlanPilotConfig, PlanPaths, FieldConfig
│   ├── provider.py                     # Provider ABC
│   ├── renderer.py                     # BodyRenderer ABC, RenderContext
│   └── exceptions.py                   # PlanPilotError hierarchy
│
├── plan/                               # L2 Core — Plan loading, validation, hashing
│   ├── __init__.py
│   ├── loader.py                       # PlanLoader
│   ├── validator.py                    # PlanValidator
│   └── hasher.py                       # PlanHasher
│
├── auth/                               # L2 Core — Token resolution
│   ├── __init__.py
│   ├── base.py                         # TokenResolver ABC
│   ├── factory.py                      # create_token_resolver()
│   ├── gh_cli.py                       # GhCliTokenResolver
│   ├── env.py                          # EnvTokenResolver
│   └── static.py                       # StaticTokenResolver
│
├── renderers/                          # L2 Core — Body rendering
│   ├── __init__.py
│   ├── factory.py                      # create_renderer()
│   └── markdown.py                     # MarkdownRenderer + helpers
│
├── engine/                             # L2 Core — Sync orchestration
│   ├── __init__.py
│   ├── engine.py                       # SyncEngine
│   └── utils.py                        # parse_metadata_block, compute_parent_blocked_by
│
├── providers/                          # L2 Core — Provider adapters
│   ├── __init__.py
│   ├── base.py                         # ProviderContext base class
│   ├── factory.py                      # create_provider()
│   ├── dry_run.py                      # DryRunProvider
│   └── github/                         # GitHub concrete adapter
│       ├── __init__.py
│       ├── provider.py                 # GitHubProvider
│       ├── item.py                     # GitHubItem
│       ├── models.py                   # GitHubProviderContext, ResolvedField
│       ├── mapper.py                   # URL parsing, option resolution
│       ├── schema.graphql              # Vendored GitHub GraphQL schema
│       ├── operations/                 # .graphql operation files
│       │   ├── fetch_repo.graphql
│       │   ├── create_label.graphql
│       │   ├── fetch_project.graphql
│       │   ├── fetch_project_items.graphql
│       │   ├── search_issues.graphql
│       │   ├── create_issue.graphql
│       │   ├── update_issue.graphql
│       │   ├── add_project_item.graphql
│       │   ├── update_project_field.graphql
│       │   ├── add_sub_issue.graphql
│       │   ├── add_blocked_by.graphql
│       │   └── fetch_relations.graphql
│       └── github_gql/                 # Generated by ariadne-codegen (committed)
│           ├── __init__.py
│           ├── client.py
│           ├── input_types.py
│           ├── enums.py
│           └── ...
│
├── sdk.py                              # L3 — PlanPilot, load_config(), load_plan()
├── cli.py                              # L4 — Arg parsing, output formatting
│
├── implementation/                     # Implementation guides (you are here)
│   ├── README.md                       # Index with links to all phase docs
│   ├── 00-overview.md                  # This file
│   ├── 01-test-infrastructure.md
│   ├── 02-phase0-contracts.md
│   ├── 03-phase1-plan.md
│   ├── 04-phase1-auth.md
│   ├── 05-phase1-renderers.md
│   ├── 06-phase1-engine.md
│   ├── 07-phase2-providers-base.md
│   ├── 08-phase2-github-provider.md
│   ├── 09-phase3-sdk.md
│   ├── 10-phase4-cli.md
│   └── 11-phases-and-dependencies.md
│
└── docs/                               # Design specs (reference)
    ├── design/
    ├── modules/
    └── decisions/
```

### Tests (`tests/`)

```text
tests/
├── __init__.py
├── conftest.py                         # Shared v2 fixtures
├── fakes/                              # Shared test doubles
│   ├── __init__.py
│   ├── provider.py                     # FakeProvider + FakeItem
│   └── renderer.py                     # FakeRenderer
├── fixtures/                           # JSON test data
│   └── plans/
│       ├── minimal_unified.json
│       ├── multi_file_epics.json
│       ├── multi_file_stories.json
│       ├── multi_file_tasks.json
│       ├── full_plan.json
│       └── invalid/
│           ├── duplicate_ids.json
│           ├── bad_parent_ref.json
│           └── missing_required.json
├── contracts/
│   ├── __init__.py
│   ├── test_plan_types.py
│   ├── test_item_types.py
│   ├── test_sync_types.py
│   ├── test_config_types.py
│   └── test_exceptions.py
├── plan/
│   ├── __init__.py
│   ├── test_loader.py
│   ├── test_validator.py
│   └── test_hasher.py
├── auth/
│   ├── __init__.py
│   ├── test_gh_cli.py
│   ├── test_env.py
│   ├── test_static.py
│   └── test_factory.py
├── renderers/
│   ├── __init__.py
│   ├── test_markdown.py
│   └── test_factory.py
├── engine/
│   ├── __init__.py
│   └── test_engine.py
├── providers/
│   ├── __init__.py
│   └── github/
│       ├── __init__.py
│       ├── test_provider.py
│       ├── test_item.py
│       ├── test_mapper.py
│       └── test_models.py
├── sdk/
│   ├── __init__.py
│   └── test_sdk.py
└── cli/
    ├── __init__.py
    └── test_cli.py
```

---

## Branching and Workflow

### Branch Structure

```text
main
 └── v2                          (umbrella, created from main)
      ├── v2/contracts           (Phase 0 — foundation types + ABCs + exceptions)
      ├── v2/test-infra          (Phase 0 — FakeProvider, FakeRenderer, shared fixtures)
      ├── v2/plan                (Phase 1 — PlanLoader, PlanValidator, PlanHasher)
      ├── v2/auth                (Phase 1 — TokenResolver ABC + 3 resolvers + factory)
      ├── v2/renderers           (Phase 1 — MarkdownRenderer + factory)
      ├── v2/engine              (Phase 1 — SyncEngine 5-phase pipeline)
      ├── v2/github-provider     (Phase 2 — codegen + GitHubProvider + GitHubItem)
      ├── v2/sdk                 (Phase 3 — PlanPilot class + load_config + re-exports)
      └── v2/cli                 (Phase 4 — subcommand parser + output formatting)
```

Feature branches merge into `v2` via PR. When v2 is complete, `v2` merges into `main` as 2.0.0.

### TDD Cycle (every module)

1. Write failing tests first (based on specs in the phase docs)
2. Implement minimum code to pass
3. Run checks:
   ```bash
   pytest tests/ -v                           # v2 tests only
   ruff check src/planpilot/ tests/        # lint
   ruff format src/planpilot/ tests/       # format
   mypy src/planpilot/                        # type check
   ```
4. Commit on green (Conventional Commits format)

### Commit Message Convention

```text
feat(contracts): add PlanItem and Plan models
feat(engine): implement discovery phase
test(plan): add PlanValidator strict mode tests
fix(auth): handle empty gh auth token output
```
