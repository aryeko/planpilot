# PlanPilot v2 — Implementation Guide

> Single source of truth for agents implementing v2.
> Each file is self-contained — read only the file you need for your current task.

**Generated:** 2026-02-09

---

## Start Here

| Doc | What it covers | Read when... |
|-----|---------------|--------------|
| [Overview](./00-overview.md) | Architecture, code placement, package structure, branching, TDD workflow | Starting any v2 work — read this first |
| [Test Infrastructure](./01-test-infrastructure.md) | FakeProvider, FakeRenderer, shared conftest fixtures | Building or consuming test doubles |

## Phase 0 — Foundation (must be first)

| Doc | Module | Branch |
|-----|--------|--------|
| [Contracts](./02-phase0-contracts.md) | All contract types, ABCs, exception hierarchy | `v2/contracts` |

## Phase 1 — Core Modules (all parallel)

| Doc | Module | Branch |
|-----|--------|--------|
| [Plan](./03-phase1-plan.md) | PlanLoader, PlanValidator, PlanHasher | `v2/plan` |
| [Auth](./04-phase1-auth.md) | TokenResolver ABC + 3 resolvers + factory | `v2/auth` |
| [Renderers](./05-phase1-renderers.md) | MarkdownRenderer + factory | `v2/renderers` |
| [Engine](./06-phase1-engine.md) | SyncEngine 5-phase pipeline + utils | `v2/engine` |

## Phase 2 — GitHub Provider (can overlap with Phase 1)

| Doc | Module | Branch |
|-----|--------|--------|
| [Providers Base](./07-phase2-providers-base.md) | ProviderContext, factory, DryRunProvider | `v2/github-provider` |
| [GitHub Provider](./08-phase2-github-provider.md) | Codegen + GitHubProvider + GitHubItem + mapper + retry | `v2/github-provider` |

## Phase 3 — SDK (after all Core merges)

| Doc | Module | Branch |
|-----|--------|--------|
| [SDK](./09-phase3-sdk.md) | PlanPilot class, load_config, load_plan, re-exports | `v2/sdk` |

## Phase 4 — CLI (after SDK merges)

| Doc | Module | Branch |
|-----|--------|--------|
| [CLI](./10-phase4-cli.md) | Subcommand parser, output formatting, exit codes | `v2/cli` |

## Reference

| Doc | Contents |
|-----|----------|
| [Phases and Dependencies](./11-phases-and-dependencies.md) | Dependency graph, phase details, merge order, new dependencies |

## Design Docs (deep-dive reference)

All original design specs live in `../docs/`:

| Doc | Path |
|-----|------|
| Architecture | [`../docs/design/architecture.md`](../docs/design/architecture.md) |
| Contracts | [`../docs/design/contracts.md`](../docs/design/contracts.md) |
| Engine | [`../docs/design/engine.md`](../docs/design/engine.md) |
| Plan | [`../docs/modules/plan.md`](../docs/modules/plan.md) |
| Providers | [`../docs/modules/providers.md`](../docs/modules/providers.md) |
| GitHub Provider | [`../docs/modules/github-provider.md`](../docs/modules/github-provider.md) |
| Auth | [`../docs/modules/auth.md`](../docs/modules/auth.md) |
| Renderers | [`../docs/modules/renderers.md`](../docs/modules/renderers.md) |
| Config | [`../docs/modules/config.md`](../docs/modules/config.md) |
| SDK | [`../docs/modules/sdk.md`](../docs/modules/sdk.md) |
| CLI | [`../docs/modules/cli.md`](../docs/modules/cli.md) |
| ADR-001 | [`../docs/decisions/001-ariadne-codegen.md`](../docs/decisions/001-ariadne-codegen.md) |
