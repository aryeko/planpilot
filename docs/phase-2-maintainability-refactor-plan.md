# Phase 2 - Maintainability Refactor Plan

## Motivation

Phase 1 restored architectural correctness (layer boundaries, SDK drift reduction, and boundary guardrails). The codebase is now behaviorally stable and well-protected, but key modules are still dense (`cli.py`, `sdk.py`, `providers/github/provider.py`).

This phase focuses on maintainability improvements so future changes are easier to review, test, and reason about, without changing user-visible behavior.

## Phase 2.5 Follow-up (Completed)

After initial Phase 2 extraction, `sdk_ops/*` was intentionally collapsed back into `src/planpilot/sdk.py` to reduce unnecessary indirection while preserving behavior and compatibility hooks. This was a structural simplification, not a behavior change.

Current source-of-truth (post-2.5):

- `src/planpilot/sdk.py` owns sync/map-sync/clean orchestration and sync-map persistence hooks.
- `src/planpilot/sdk_ops/*` has been removed.
- Boundary tests now validate `sdk.py` import hygiene directly.

This update supersedes earlier Slice 4/5 destination references to `sdk_ops/*`.

## Goals

1. Reduce responsibility density in hotspot modules.
2. Improve locality of changes by decomposing workflows into focused modules.
3. Preserve all external behavior and public API contracts.
4. Strengthen boundary protections to prevent future architecture drift.
5. Keep type safety and test reliability high throughout the refactor.

## Non-Goals

- No changes to CLI flags, outputs, or exit-code mapping.
- No changes to sync/map-sync/clean semantics.
- No provider capability changes or GraphQL operation redesign.
- No documentation alignment work beyond this plan artifact (handled in Phase 4).
- No root namespace/domain consolidation (`cli`/`sdk` top-level ownership); that is handled in Phase 3.

## Suggested Solution

Implement the refactor in small, reviewable slices, each independently reversible.

### Target File Map

Phase 2 uses explicit destination modules so decomposition is predictable and reviewable.

- CLI package split (command-oriented):
  - `src/planpilot/cli/__init__.py` (public CLI entry exports)
  - `src/planpilot/cli/app.py` (main dispatch + top-level exit mapping)
  - `src/planpilot/cli/parser.py` (root parser + subcommand wiring)
  - `src/planpilot/cli/common.py` (shared CLI helpers)
  - `src/planpilot/cli/commands/sync.py` (args + execution + summary)
  - `src/planpilot/cli/commands/clean.py` (args + execution + summary)
  - `src/planpilot/cli/commands/init.py` (args + execution + interactive/default flow)
  - `src/planpilot/cli/commands/map_sync.py` (args + execution + summary)

- Init domain stays separate from CLI package (not CLI-only concern):
  - `src/planpilot/init/auth.py`
  - `src/planpilot/init/validation.py`

- SDK internals (post-2.5):
  - `src/planpilot/sdk.py` (public facade + current orchestration internals)

- GitHub provider internal split (while keeping context/lifecycle in `provider.py`):
  - `src/planpilot/providers/github/ops/__init__.py`
  - `src/planpilot/providers/github/ops/crud.py`
  - `src/planpilot/providers/github/ops/relations.py`
  - `src/planpilot/providers/github/ops/labels.py`
  - `src/planpilot/providers/github/ops/project.py`
  - `src/planpilot/providers/github/ops/convert.py`

### Suggested Repo Structure

```text
src/planpilot/
|- cli/
|  |- __init__.py
|  |- app.py
|  |- parser.py
|  |- common.py
|  `- commands/
|     |- sync.py
|     |- clean.py
|     |- init.py
|     `- map_sync.py
|- init/
|  |- __init__.py
|  |- auth.py
|  `- validation.py
|- sdk.py
`- providers/github/
   |- provider.py
   `- ops/
      |- __init__.py
      |- crud.py
      |- relations.py
      |- labels.py
      |- project.py
      `- convert.py
```

### Slice 1 - CLI parser extraction

- Convert `src/planpilot/cli.py` into package form (`src/planpilot/cli/`).
- Add `src/planpilot/cli/parser.py` with root parser + subcommand wiring.
- Add `src/planpilot/cli/app.py` and `src/planpilot/cli/commands/*` stubs with unchanged behavior.
- Keep `src/planpilot/cli/__init__.py` exporting `build_parser` and `main` for compatibility.

### Slice 2 - CLI formatting extraction

- Move summary-formatting logic into command modules:
  - `commands/sync.py`
  - `commands/clean.py`
  - `commands/map_sync.py`
- Place shared output utilities in `src/planpilot/cli/common.py`.
- Keep output text stable (including spacing and dry-run notices).

### Slice 3 - CLI init workflow decomposition

- Move init command flow into `src/planpilot/cli/commands/init.py`.
- Keep domain auth/validation logic in `src/planpilot/init/*` and call through public APIs.
- Keep command flow and exit behavior unchanged.

### Slice 4 - SDK sync/map orchestration extraction (completed then simplified in 2.5)

- Kept `PlanPilot` as public facade in `src/planpilot/sdk.py`.
- Initial extraction to `sdk_ops/*` was completed, then collapsed back into `sdk.py` in Phase 2.5 to reduce indirection.

### Slice 5 - SDK clean and persistence extraction (completed then simplified in 2.5)

- Preserved `PlanPilot.clean()` contract and deletion semantics.
- Final post-2.5 location for these internals is `src/planpilot/sdk.py`.

### Slice 6 - GitHub provider context/CRUD split

- Decompose `providers/github/provider.py` internals by concern:
  - keep context/setup and lifecycle in `providers/github/provider.py`
  - CRUD/search -> `providers/github/ops/crud.py`
  - relation helpers -> `providers/github/ops/relations.py`
- Keep `GitHubProvider` public behavior and contract unchanged.

### Slice 7 - Provider helper split + guardrail tightening

- Further split helper concerns into `providers/github/ops/labels.py`, `providers/github/ops/project.py`, and `providers/github/ops/convert.py`.
- Add/extend layer boundary tests to cover new modules and prevent regressions.

## Validation Approach

Each slice should run both fast targeted verification and full repository gates.

### Slice-level fast verification

- CLI slices: run targeted CLI tests (`tests/test_cli*.py`, relevant e2e tests when init flow changes).
- SDK slices: run `tests/test_sdk.py` and `tests/test_sdk_map_sync.py`.
- Provider slices: run `tests/providers/github/test_provider.py` and related provider tests.
- Boundary slices: run `tests/test_layer_boundaries.py` and `tests/test_cli_layer_boundary.py` (and any added SDK boundary tests).

### Full gate per slice

- `poetry run poe check`

### Acceptance criteria

1. All tests/type/lint gates pass.
2. No public API breakage in `planpilot` exports unless explicitly approved.
3. No CLI behavior drift (flags, summaries, exit codes).
4. Boundary guardrails remain green and stricter than pre-refactor.

## Risks and Controls

### High risks

- Output/exit-code drift in CLI decomposition.
- Behavior drift in GitHub provider create/update/relation paths.

Controls:

- Exact output assertions for summaries.
- Preserve existing provider behavior through facade wrappers and targeted tests.

### Medium risks

- Import cycles introduced by module movement.
- Private-method test coupling breakage during provider decomposition.

Controls:

- Keep moves incremental.
- Add AST-based import boundary tests per slice.

### Low risks

- Type annotation churn and minor refactor noise.

Controls:

- Run mypy and full `poe check` at each slice boundary.

## Rollout Strategy

- One slice per PR/commit group.
- Validate and stabilize each slice before starting the next.
- If a slice regresses behavior, revert only that slice and continue from last green boundary.
