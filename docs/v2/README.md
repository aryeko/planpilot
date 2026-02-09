# PlanPilot v2 Architecture

This directory contains the architecture documentation for PlanPilot v2, a complete redesign focused on SDK-first development with clean layered architecture.

## Design Goals

- **SDK-first** — The CLI is a thin wrapper around a fully-functional SDK. Users can integrate PlanPilot programmatically without touching the CLI.

- **Clean layered architecture** — Strict downward-only dependencies with four distinct layers: Contracts, Core, SDK, and CLI. Each layer has clear responsibilities and cannot bypass layers.

- **Adapter pattern** — Both providers (GitHub, Jira, Linear) and renderers (Markdown, wiki) are pluggable adapters. The core engine knows nothing about concrete implementations.

- **SOLID principles** — Object-oriented design throughout. Single responsibility, dependency inversion, open/closed principle enforced by layer boundaries.

- **Async-first** — All I/O operations are async. The SDK and engine are fully async-compatible.

- **Launch scope** — v2 launch is GitHub-first. Adapter contracts remain provider-agnostic, but non-GitHub providers are future extension work.

## Documentation

- **[Architecture](./architecture.md)** — Complete architectural specification with layer diagrams, dependency rules, UML class diagrams, and extension guides.
- **[Engine](./engine.md)** — Sync engine module spec with 5-phase pipeline and contracts requirements.
- **[Plan](./plan.md)** — Plan module spec covering loading, validation, and hashing.
- **[Providers](./providers.md)** — Provider module spec with GitHub adapter structure.
- **[Renderers](./renderers.md)** — Renderer module spec with Markdown implementation.
- **[Config](./config.md)** — Config module spec with JSON-loadable configuration models.
- **[SDK](./sdk.md)** — SDK module spec defining the public API facade.
- **[CLI](./cli.md)** — CLI module spec with config-file-driven interface.
- **[GitHub Provider Research](./github-provider-research.md)** — Evaluation of implementation approaches for the GitHub provider (githubkit, ariadne-codegen, gh CLI, etc.).

## Locked v2 Decisions

- Discovery is provider-search-first using metadata marker query (`PLAN_ID:<plan_id>`).
- All renderers emit a shared plain-text metadata block (`PLANPILOT_META_V1` ... `END_PLANPILOT_META`).
- Discovery uses provider-native search APIs (GitHub GraphQL `search`) with fail-fast behavior on truncation/capability limits.
- Reconciliation ownership is hybrid:
  - plan-authoritative: title/body/type/label/size/relations
  - provider-authoritative: status/priority/iteration after creation
- Exit codes are differentiated (`0`, `2`, `3`, `4`, `5`, `1`).
- SDK is the composition root via `PlanPilot.from_config(...)`.
- Dry-run sync maps are persisted to `<sync_path>.dry-run`.

## Review Findings Closure Matrix

| Finding Area | Resolution Location |
|--------------|---------------------|
| Discovery contract and idempotency source of truth | `engine.md`, `providers.md`, `architecture.md` |
| Renderer-agnostic marker format | `renderers.md`, `engine.md`, `architecture.md` |
| Deterministic plan hash across load order | `plan.md`, `architecture.md` |
| Reconcile behavior for existing items | `engine.md`, `providers.md` |
| Non-atomic create and partial-failure recovery | `providers.md`, `github-provider-research.md`, `architecture.md` |
| Label bootstrap and operations inventory gaps | `providers.md`, `github-provider-research.md` |
| Relation capability gating | `providers.md`, `github-provider-research.md` |
| Retry/backoff/pagination requirements | `providers.md`, `github-provider-research.md` |
| Plan hierarchy/source-of-truth ambiguity | `plan.md`, `architecture.md` |
| Unified plan JSON shape clarity | `plan.md`, `config.md` |
| Auth/token validation and required project URL behavior | `config.md` |
| CLI/SDK composition and exit code clarity | `cli.md`, `sdk.md`, `architecture.md` |
| Structured partial-create failure contract | `providers.md`, `engine.md`, `architecture.md`, `github-provider-research.md` |
| Discovery capability enforcement and existing-item upsert branch | `providers.md`, `engine.md`, `architecture.md` |
| Create-type strategy (issue-type vs label) and compatibility behavior | `config.md`, `providers.md`, `github-provider-research.md` |
| Loader API and multi-file shape ambiguity | `sdk.md`, `plan.md`, `architecture.md` |
| CLI output stability contract for automation | `cli.md`, `sdk.md` |

## Known v2 Limitations

- Engine execution remains sequential (epics -> stories -> tasks); concurrent provider operations are not required.
- Workflow board fields (`status`, `priority`, `iteration`) are provider-authoritative after create and not plan-controlled in v2.
- Relation mutations are capability-gated and produce explicit errors when configured features are unavailable.
- CLI text summary is human-oriented and not a stable machine interface; automation should use SDK APIs.
