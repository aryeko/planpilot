# Phase 3 - SDK/CLI Responsibility Consolidation Plan

## Objective

Consolidate responsibilities so runtime behavior remains unchanged while ownership becomes explicit:

- SDK methods are programmatic workflows that return result objects.
- CLI commands orchestrate user-facing flow and decide when to persist side effects.
- Persistence helpers live in neutral modules (not in CLI and not embedded in SDK facade orchestration paths).

## Non-Goals

- No CLI flag or exit-code changes.
- No sync/map-sync/clean behavior drift.
- No provider capability changes.
- No broad namespace migration of all root modules under `sdk/`.

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

### Neutral persistence-owned

- Sync-map read/write policy helpers.
- Remote plan persistence helpers.

## Phases

### Phase 3.1 - Introduce neutral persistence module

Files:

- `src/planpilot/persistence/__init__.py`
- `src/planpilot/persistence/sync_map.py`
- `src/planpilot/persistence/remote_plan.py`

Actions:

1. Move sync-map path/read/write helpers from `sdk.py` into `persistence/sync_map.py`.
2. Move remote plan persistence helper from SDK internals to `persistence/remote_plan.py`.
3. Keep temporary SDK wrappers that delegate to persistence module (compatibility bridge).

Validation:

- `poetry run pytest tests/test_sdk.py tests/test_sdk_map_sync.py`
- `poetry run poe check`

Checkpoint:

- No behavior changes; wrappers still satisfy existing monkeypatch tests.

---

### Phase 3.2 - Make SDK workflows pure by default

Files:

- `src/planpilot/sdk.py`
- `tests/test_sdk.py`
- `tests/test_sdk_map_sync.py`

Actions:

1. Refactor `PlanPilot.sync()` and `PlanPilot.map_sync()` to return results without writing local files.
2. Keep `clean()` semantics unchanged (provider-side deletes are intrinsic operation side effects).
3. Add explicit SDK helper methods for persistence calls (delegating to neutral persistence modules).

Validation:

- RED/GREEN tests asserting no local write side effects in `sync()` and `map_sync()`.
- Existing compatibility hook tests remain green or are replaced with explicit persistence-path tests.
- `poetry run pytest tests/test_sdk.py tests/test_sdk_map_sync.py`

Checkpoint:

- SDK behavior is pure for local persistence side effects and fully test-covered.

---

### Phase 3.3 - Wire CLI commands to explicit persistence

Files:

- `src/planpilot/cli/commands/sync.py`
- `src/planpilot/cli/commands/map_sync.py`
- `tests/test_cli.py`
- `tests/test_cli_map_sync.py`

Actions:

1. After SDK workflow returns, CLI calls persistence helpers according to mode (`--dry-run` vs `--apply`).
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

## Commit Strategy

1. `refactor(persistence): add neutral persistence modules and sdk delegation`
2. `refactor(sdk): make sync and map_sync workflows side-effect free`
3. `refactor(cli): persist sync and map-sync artifacts explicitly in commands`
4. `test(architecture): tighten boundaries for sdk-cli-persistence ownership`
5. `docs(architecture): align sdk/cli ownership model`

## Done Criteria

- SDK `sync` and `map_sync` return results without local file writes.
- CLI commands explicitly own local persistence orchestration.
- Neutral persistence modules are the only local state-write implementation point.
- No CLI behavior drift (flags, output text, exit codes, dry-run/apply semantics).
- `poetry run poe check` and `tests/e2e/test_cli_e2e.py` are green.
- Architecture docs and boundary tests match final implementation.
