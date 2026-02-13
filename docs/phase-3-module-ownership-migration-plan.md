# Phase 3 - Module Ownership Migration Plan

## Purpose

Define a concrete module-by-module migration to enforce clear ownership between CLI and SDK domains.

Agreed ownership model:

- `metadata` -> SDK only
- `progress` -> CLI-owned observer wiring (SDK consumes protocol only)
- `scaffold` -> CLI-only
- `init` -> CLI-only
- `map_sync` -> SDK-only (CLI uses result and writes)
- `persistence` -> CLI-only (CLI protocol specific)
- `auth` -> SDK-owned; CLI init uses SDK API
- `targets` -> init/scaffold concern

## Constraints

- Preserve CLI behavior, flags, output text, and exit codes.
- Preserve `planpilot` public API unless explicitly called out.
- Prefer incremental moves with compatibility shims and review checkpoints.

## Mapping Table

| Current path | Owner | Proposed destination | Rationale |
|---|---|---|---|
| `src/planpilot/cli/*` | CLI | `src/planpilot/cli/*` | Existing CLI domain stays canonical interface layer |
| `src/planpilot/metadata.py` | SDK | `src/planpilot/core/metadata.py` + shim | Metadata parsing is SDK runtime concern |
| `src/planpilot/progress.py` | CLI | `src/planpilot/cli/progress/rich.py` + shim | CLI owns progress presentation/wiring |
| `src/planpilot/config/scaffold.py` | CLI | `src/planpilot/cli/scaffold/config_builder.py` + shim | Scaffold is CLI protocol/workflow concern |
| `src/planpilot/init/validation.py` | CLI | `src/planpilot/cli/init/validation.py` + shim | Init flow concern |
| `src/planpilot/init/auth.py` | SDK | `src/planpilot/core/auth/preflight.py` + shim | Auth logic belongs to SDK; CLI consumes SDK API |
| `src/planpilot/map_sync/*` | SDK | `src/planpilot/core/map_sync/*` + shim package | Reconciliation is SDK workflow concern |
| `src/planpilot/persistence/*` | CLI | `src/planpilot/cli/persistence/*` + shim package | CLI protocol-specific local artifact writes |
| `src/planpilot/auth/*` | SDK | `src/planpilot/core/auth/*` + shim package | Auth ownership consolidated in SDK |
| `src/planpilot/targets/*` | CLI | `src/planpilot/cli/scaffold/targets/*` + shim package | Targets are init/scaffold concern |
| `src/planpilot/sdk.py` | SDK | keep `sdk.py` facade; internals in `core/*` | Preserve import stability |
| `src/planpilot/contracts/*` | SDK | `src/planpilot/core/contracts/*` + shim package | Core contracts belong with programmatic runtime |
| `src/planpilot/engine/*` | SDK | `src/planpilot/core/engine/*` + shim package | Runtime orchestration is core programmatic logic |
| `src/planpilot/providers/*` | SDK | `src/planpilot/core/providers/*` + shim package | Providers are SDK runtime dependencies |
| `src/planpilot/plan/*` | SDK | `src/planpilot/core/plan/*` + shim package | Plan parsing/validation is core runtime logic |
| `src/planpilot/renderers/*` | SDK | `src/planpilot/core/renderers/*` + shim package | Rendering logic is SDK runtime domain |
| `src/planpilot/clean/*` | SDK | `src/planpilot/core/clean/*` + shim package | Clean workflow helpers are SDK runtime logic |

## Migration Phases

### Phase 1 - Destination namespaces + compatibility shims

**Objective**
- Introduce `core/*` and CLI-owned subpackages without behavior changes.

**Key edits**
- Add: `src/planpilot/core/`
- Add: `src/planpilot/cli/progress/`, `src/planpilot/cli/persistence/`, `src/planpilot/cli/scaffold/`, `src/planpilot/cli/init/`
- Add temporary shims at old paths re-exporting new modules.

**Tests**
- `poetry run pytest tests/test_cli_package_structure.py tests/test_layer_boundaries.py`

**Risks**
- Import cycles from shims.
- Incorrect re-export wiring.

---

### Phase 2 - Move CLI-owned modules

**Objective**
- Move progress/persistence/scaffold/init-validation/targets into CLI-owned paths.

**Key edits**
- Move implementations into `src/planpilot/cli/...` destinations.
- Update CLI command imports to new paths.
- Keep old modules as deprecation shims.

**Tests**
- `poetry run pytest tests/test_cli.py tests/test_cli_map_sync.py tests/test_scaffold.py tests/test_cli_auth_preflight.py`

**Risks**
- Dry-run map path or sync-map persistence regressions.

---

### Phase 3 - Consolidate auth ownership in SDK

**Objective**
- Move init-auth logic under SDK auth and have CLI init call SDK API only.

**Key edits**
- Move `init/auth.py` logic to `core/auth/preflight.py`.
- Expose SDK auth API via `planpilot.auth` or `planpilot.__init__`.
- Refactor CLI init flow to consume SDK API.

**Tests**
- `poetry run pytest tests/auth tests/test_cli_auth_preflight.py tests/test_cli.py`

**Risks**
- GH scope/owner-type behavior drift.

---

### Phase 4 - Move map_sync + metadata to SDK-owned internals

**Objective**
- Finalize SDK-only ownership for map-sync and metadata.

**Key edits**
- Move `map_sync/*` and `metadata.py` under `core/`.
- Update `sdk.py` imports.
- Keep compatibility shims at old paths.

### Phase 4.5 - Consolidate remaining core runtime domains under `core/`

**Objective**
- Physically group all programmatic runtime domains under `src/planpilot/core/`.

**Key edits**
- Move `contracts/`, `engine/`, `providers/`, `plan/`, `renderers/`, and `clean/` under `core/`.
- Keep root-level package shims (`src/planpilot/contracts`, etc.) re-exporting from `core/*` during migration window.
- Update imports incrementally to prefer `planpilot.core.*` internally.

**Tests**
- `poetry run pytest`
- `poetry run poe check`

**Risks**
- Large import-path churn and potential circular imports.
- Shim complexity during transition.

**Tests**
- `poetry run pytest tests/test_sdk.py tests/test_sdk_map_sync.py tests/test_cli_map_sync.py`

**Risks**
- Reconcile semantics drift.

---

### Phase 5 - Boundary enforcement and cleanup

**Objective**
- Lock architecture ownership rules and remove cross-layer leakage.

**Key edits**
- Tighten AST boundary tests.
- Keep shims for one deprecation window, then remove.

**Tests**
- `poetry run pytest tests/test_layer_boundaries.py tests/test_cli_layer_boundary.py`
- `poetry run poe check`

**Risks**
- Hidden legacy imports in tests/fakes.

---

### Phase 6 - Documentation alignment

**Objective**
- Make docs match final ownership and migration policy.

**Key edits**
- Update `docs/modules/sdk.md`, `docs/modules/cli.md`, `docs/design/architecture.md`.
- Add deprecation and migration notes.

**Tests/validation**
- `poetry run pytest tests/test_main_module.py tests/test_cli_package_structure.py`
- Sanity-check all documented paths exist.

## Post-Migration Import Rules

- `planpilot/sdk.py` and `planpilot/core/**` MUST NOT import `planpilot/cli/**`.
- `planpilot/cli/**` may import:
  - `planpilot` public API,
  - `planpilot/cli/**`,
  - approved CLI-owned helpers (`planpilot/cli/persistence/**`, `planpilot/cli/progress/**`).
- `planpilot/core/**` MUST remain CLI-agnostic.
- Root shim modules may re-export across layers temporarily, but internal code should import owned destinations directly.

## Final Target Tree (Sketch)

```text
src/planpilot/
  __init__.py
  __main__.py
  sdk.py
  cli/
    app.py
    parser.py
    commands/
    progress/
      rich.py
    persistence/
      sync_map.py
      remote_plan.py
    scaffold/
      config_builder.py
      targets/
        github_project.py
    init/
      validation.py
  core/
    auth/
      preflight.py
      factory.py
      resolvers/
    map_sync/
      parser.py
      reconciler.py
    config/
      loader.py
    metadata.py
    contracts/
    engine/
    providers/
    plan/
    renderers/
    clean/
  # temporary compatibility shims during migration:
  auth/
  contracts/
  engine/
  map_sync/
  init/
  clean/
  providers/
  plan/
  renderers/
  targets/
  persistence/
  progress.py
  metadata.py
```

## Done Criteria

- Ownership model is reflected in module locations and imports.
- CLI behavior is unchanged.
- SDK public API remains stable (unless explicitly versioned/deprecated).
- Boundary tests enforce new ownership.
- Docs match final structure and deprecation policy.
