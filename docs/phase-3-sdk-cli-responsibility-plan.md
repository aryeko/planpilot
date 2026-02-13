# Phase 3 - SDK/CLI Responsibility Consolidation Plan

## Objective

Consolidate responsibilities so runtime behavior remains unchanged while ownership becomes explicit:

- SDK methods are programmatic workflows that return result objects.
- CLI commands orchestrate user-facing flow and decide when to persist side effects.
- Persistence helpers are CLI protocol-owned modules and are not embedded in SDK facade orchestration paths.

Phase 3 naming convention update:

- Runtime programmatic domains are consolidated under `src/planpilot/core/`.
- `src/planpilot/sdk.py` remains a stable facade/import anchor.

## Non-Goals

- No CLI flag or exit-code changes.
- No sync/map-sync/clean behavior drift.
- No provider capability changes.
- No broad namespace migration under `sdk/` itself; use `core/` for runtime domains.

## Baseline (Current)

- `src/planpilot/cli/` is decomposed and stable.
- `src/planpilot/sdk.py` currently contains orchestration + persistence hooks.
- `providers/github/ops/*` split is in place.
- Quality gates and e2e are green.

## Target Ownership

### CLI-owned

- Arg parsing, prompts, summary formatting, exit mapping.
- Deciding when to persist side effects for `sync` and `map sync`.

### SDK-owned

- Programmatic workflow semantics for `sync`, `map_sync`, `clean`.
- Provider orchestration and domain result construction.

### CLI persistence-owned

- Sync-map read/write policy helpers (`cli/persistence`).
- Remote plan persistence helpers (`cli/persistence`).

## Phases

### Phase 3.1 - Introduce CLI-owned persistence module

Files:

- `src/planpilot/cli/persistence/__init__.py`
- `src/planpilot/cli/persistence/sync_map.py`
- `src/planpilot/cli/persistence/remote_plan.py`

Actions:

1. Move sync-map path/read/write helpers from `sdk.py` into `cli/persistence/sync_map.py`.
2. Move remote plan persistence helper from SDK internals to `cli/persistence/remote_plan.py`.
3. Keep temporary shim bridge from legacy `src/planpilot/persistence/*` paths.

Validation:

- `poetry run pytest tests/test_sdk.py tests/test_sdk_map_sync.py`
- `poetry run poe check`

Checkpoint:

- No behavior changes; CLI persists using owned protocol modules.

---

### Phase 3.2 - Make SDK workflows pure by default

Files:

- `src/planpilot/sdk.py`
- `src/planpilot/core/**` (as introduced by ownership migration)
- `tests/test_sdk.py`
- `tests/test_sdk_map_sync.py`

Actions:

1. Refactor `PlanPilot.sync()` and `PlanPilot.map_sync()` to return results without writing local files.
2. Keep `clean()` semantics unchanged (provider-side deletes are intrinsic operation side effects).
3. Remove SDK persistence helper APIs; SDK returns objects only.

Validation:

- RED/GREEN tests asserting no local write side effects in `sync()` and `map_sync()`.
- Existing compatibility tests are updated to assert persistence is CLI-owned.
- `poetry run pytest tests/test_sdk.py tests/test_sdk_map_sync.py`

Checkpoint:

- SDK behavior is pure for local persistence side effects and fully test-covered.

---

### Phase 3.3 - Wire CLI commands to explicit persistence

Files:

- `src/planpilot/cli/commands/sync.py`
- `src/planpilot/cli/commands/map_sync.py`
- `src/planpilot/cli/persistence/*`
- `tests/test_cli.py`
- `tests/test_cli_map_sync.py`

Actions:

1. After SDK workflow returns, CLI calls CLI-owned persistence helpers according to mode (`--dry-run` vs `--apply`).
2. Preserve output text and existing UX.
3. Keep `map sync` plan-id selection behavior unchanged.

Validation:

- `poetry run pytest tests/test_cli.py tests/test_cli_map_sync.py`
- `poetry run pytest tests/e2e/test_cli_e2e.py`
- `poetry run poe check`

Checkpoint:

- CLI-visible behavior unchanged with explicit persistence ownership.

---

### Phase 3.4 - Tighten architecture tests and docs

Files:

- `tests/test_layer_boundaries.py`
- `tests/test_cli_layer_boundary.py`
- `docs/modules/sdk.md`
- `docs/modules/cli.md`
- `docs/design/architecture.md`

Actions:

1. Assert SDK does not depend on CLI.
2. Assert CLI depends only on public API + approved persistence boundary.
3. Update docs to reflect final ownership model.

Validation:

- `poetry run pytest tests/test_layer_boundaries.py tests/test_cli_layer_boundary.py`
- `poetry run poe check`

Checkpoint:

- Final architecture and docs are aligned and enforced.

---

### Phase 3.5 - Remove temporary compatibility shims

Files:

- `src/planpilot/persistence/*` (legacy shim package)
- Any remaining temporary root shims introduced during ownership migration

Actions:

1. Remove shim modules after migration window closes.
2. Update internal imports to final owned paths only.
3. Remove shim-specific tests and deprecation warnings.

Validation:

- `poetry run pytest`
- `poetry run poe check`
- `poetry run pytest tests/e2e/test_cli_e2e.py`

Checkpoint:

- No runtime code depends on deprecated shim paths.

## Commit Strategy

1. `refactor(cli): add cli-owned persistence modules and migration shims`
2. `refactor(sdk): make sync and map_sync workflows side-effect free`
3. `refactor(cli): persist sync and map-sync artifacts explicitly in commands`
4. `refactor(core): move runtime domains under core with compatibility shims`
5. `test(architecture): tighten boundaries for core-cli-persistence ownership`
6. `docs(architecture): align sdk/cli ownership model`
7. `chore!: remove temporary ownership migration shims`

## Done Criteria

- SDK `sync` and `map_sync` return results without local file writes.
- CLI commands explicitly own local persistence orchestration.
- CLI persistence modules are the only local state-write implementation point.
- No CLI behavior drift (flags, output text, exit codes, dry-run/apply semantics).
- `poetry run poe check` and `tests/e2e/test_cli_e2e.py` are green.
- Architecture docs and boundary tests match final implementation.
- Temporary compatibility shims are removed at end of migration window.
