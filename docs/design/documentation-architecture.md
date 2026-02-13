# Documentation Architecture

This guide defines how documentation is organized, how it maps to runtime code, and which files should be updated for common change types.

## Information Architecture

```mermaid
flowchart TD
    Root[docs/README.md\nNavigation hub] --> Design[docs/design/\nArchitecture and behavior contracts]
    Root --> Modules[docs/modules/\nModule-level specs]
    Root --> Reference[docs/reference/\nSchemas and user-facing formats]
    Root --> Testing[docs/testing/\nVerification strategy]
    Root --> Decisions[docs/decisions/\nADR rationale]

    Design --> A1[architecture.md]
    Design --> A2[contracts.md]
    Design --> A3[engine.md]
    Design --> A4[map-sync.md]
    Design --> A5[clean.md]
    Design --> A6[repository-layout.md]

    Modules --> M1[cli.md]
    Modules --> M2[sdk.md]
    Modules --> M3[providers.md]
    Modules --> M4[github-provider.md]
    Modules --> M5[plan.md]
    Modules --> M6[config.md]
    Modules --> M7[auth.md]
    Modules --> M8[renderers.md]
```

## Code-to-Docs Ownership Map

```mermaid
flowchart LR
    CodeCore[src/planpilot/core/] --> DocDesign[docs/design/*.md]
    CodeCore --> DocModules[docs/modules/*.md]
    CodeCLI[src/planpilot/cli/] --> DocCLI[docs/modules/cli.md]
    CodeSDK[src/planpilot/sdk.py] --> DocSDK[docs/modules/sdk.md]
    CodeTests[tests/] --> DocTesting[docs/testing/e2e.md]
    CodeWorkflows[.github/workflows/] --> ReleaseGuide[RELEASE.md]
    CodeSchemas[src/planpilot/core/contracts/] --> RefSchemas[docs/reference/plan-schemas.md]
```

## Update Rules

- Update `README.md` for onboarding, CLI usage, or user-visible behavior changes.
- Update `docs/README.md` whenever docs structure or navigation changes.
- Update `docs/design/*.md` when behavior contracts or architecture constraints change.
- Update `docs/modules/*.md` when implementation details change in the corresponding runtime module.
- Update `RELEASE.md` and workflow docs when release or CI semantics change.

## What To Update For Common Changes

| Change type | Must update |
|---|---|
| CLI flags, summaries, or exit codes | `README.md`, `docs/modules/cli.md`, `docs/how-it-works.md` |
| Sync behavior (discovery/upsert/enrich/relations) | `docs/design/engine.md`, `docs/how-it-works.md`, `docs/modules/sdk.md` |
| Map sync behavior | `docs/design/map-sync.md`, `docs/modules/cli.md`, `docs/modules/sdk.md` |
| Clean behavior | `docs/design/clean.md`, `docs/modules/cli.md`, `docs/modules/sdk.md` |
| Provider internals or capability model | `docs/modules/providers.md`, `docs/modules/github-provider.md`, `docs/design/contracts.md` |
| Config schema or defaults | `README.md`, `docs/modules/config.md`, `docs/reference/plan-schemas.md` |
| CI/release hardening | `README.md` (if user-visible), `RELEASE.md` |

## Verification Checklist

- `poe check` passes.
- `poe test-e2e` passes when CLI behavior changes.
- Local markdown links resolve.
- New docs files are linked from `docs/README.md`.
