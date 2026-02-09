# PlanPilot v2 Architecture

This directory contains the architecture documentation for PlanPilot v2, a complete redesign focused on SDK-first development with clean layered architecture.

## Design Goals

- **SDK-first** — The CLI is a thin wrapper around a fully-functional SDK. Users can integrate PlanPilot programmatically without touching the CLI.

- **Clean layered architecture** — Strict downward-only dependencies with four distinct layers: Contracts, Core, SDK, and CLI. Each layer has clear responsibilities and cannot bypass layers.

- **Adapter pattern** — Both providers (GitHub, Jira, Linear) and renderers (Markdown, wiki) are pluggable adapters. The core engine knows nothing about concrete implementations.

- **SOLID principles** — Object-oriented design throughout. Single responsibility, dependency inversion, open/closed principle enforced by layer boundaries.

- **Async-first** — All I/O operations are async. The SDK and engine are fully async-compatible.

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
