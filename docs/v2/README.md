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
