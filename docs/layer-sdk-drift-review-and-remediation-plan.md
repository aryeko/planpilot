# Layer + SDK Drift Review and Remediation Plan

## Context

This document captures high-level review findings and a phased remediation plan focused on architecture drift introduced after commit `e5b7f1310dc5ada185cf7116cb37fbbef5237b7b`.

The plan is intentionally ordered to:

1. Restore architectural correctness first (layer + SDK drift).
2. Improve maintainability second (module size and responsibility split).
3. Consolidate root runtime domains third (`cli` and `sdk`).
4. Align documentation last (after code structure stabilizes).

## High-Level Review Findings

### 1) Layer boundary drift (high priority)

- Architecture docs state the CLI should depend only on the SDK public API.
- Current CLI code directly imports non-SDK internals (engine progress, provider mapper, auth resolvers).
- This weakens the intended dependency rule and makes CLI harder to evolve independently.

### 2) SDK scope drift (high priority)

- SDK docs describe `sdk.py` as composition-root/wiring with minimal business logic.
- Current `sdk.py` includes substantial operational logic (map-sync reconciliation, deletion ordering, markdown section extraction from remote bodies).
- This creates unclear ownership between composition and domain workflow behavior.

### 3) Maintainability pressure (medium priority)

- Several files are large and multi-responsibility (notably `cli.py`, `sdk.py`, GitHub provider adapter).
- This increases review cost, test blast radius, and risk of accidental coupling.

### 4) Documentation drift (medium priority)

- Multiple docs no longer exactly match implementation details (examples: provider operations inventory, factory mappings, file references, stale test baseline counts).
- Doc trust is currently good but trending at risk if not corrected.

## Remediation Plan

## Phase 1 - Restore Layer and SDK Boundaries

### Motivation

Architecture contracts are part of product quality in this repo. If boundaries drift, code review and future extension become slower and less predictable. This phase restores design integrity before any broader restructuring.

### Goals

- Re-establish CLI -> SDK-only dependency boundary.
- Re-establish SDK composition-root clarity by separating orchestration/wiring from domain-heavy helper workflows.
- Preserve current CLI behavior, exit codes, and user-facing outputs.

### Requirements

1. **CLI dependency boundary**
   - `src/planpilot/cli.py` must not import from internal core modules such as `planpilot.engine`, `planpilot.providers`, `planpilot.auth`, or contracts internals.
   - CLI should consume only `planpilot` public API exports.

2. **SDK composition clarity**
   - Move non-composition helper logic out of `sdk.py` into focused SDK-layer modules (for example: map-sync reconcile helpers, remote-to-plan parsing, deletion ordering helpers).
   - Keep `PlanPilot` public methods stable unless explicitly justified.

3. **Behavioral compatibility**
   - No breaking changes to command flags, summaries, or exit code mapping.
   - No regression in sync/map/clean semantics.

4. **Verification gate**
   - Must pass `poetry run poe check`.
   - Must pass targeted CLI/E2E coverage for `sync`, `init`, `map sync`, `clean` flows.

### Deliverables

- Refactored CLI imports and internal call paths.
- Refactored SDK module boundaries with unchanged public behavior.
- Updated tests if needed to reflect internal movement only (not behavior changes).

### Exit Criteria

- Layer rule drift resolved.
- SDK drift reduced to composition-root-aligned responsibilities.
- All quality gates green.

## Phase 2 - Maintainability Refactor

### Motivation

Once architecture boundaries are fixed, we can safely reduce cognitive load and future change risk by splitting large files into focused modules.

### Goals

- Reduce file size and responsibility density in key hotspots.
- Improve locality of changes and testability without changing behavior.
- Decompose internals without changing top-level runtime domain placement.

### Requirements

1. **CLI decomposition**
   - Separate parser construction, command handlers, formatting, and init workflow concerns into focused modules.

2. **SDK decomposition**
   - Separate sync/map/clean support logic and persistence/parsing helpers into dedicated modules.
   - This is internal decomposition only; root namespace consolidation is deferred to Phase 3.

3. **Provider decomposition**
   - Split GitHub provider internals by concern where practical (setup/context, CRUD, labels, fields, relation helpers).

4. **Regression safety**
   - Preserve external behavior and public API contracts.
   - Keep typing and tests green throughout.

5. **Boundary protection**
   - Add or tighten guardrails (tests/checks) that detect forbidden imports or layer regressions.

### Deliverables

- Smaller, focused modules in CLI/SDK/provider areas.
- Equivalent behavior with passing tests.
- Optional architecture guard checks to prevent future drift.

### Exit Criteria

- Hotspot files are reduced in scope and easier to navigate.
- No functional regressions.
- Quality gates remain green.

## Phase 3 - Namespace Consolidation (CLI + SDK Top-Level Domains)

### Motivation

After Phase 2 decomposition, runtime concerns are cleaner but still distributed across many top-level packages. Consolidating into explicit `cli` and `sdk` top-level domains improves discoverability and reinforces architectural intent (interface vs core) without changing behavior.

### Goals

- Keep `cli` as the user interface entry domain.
- Consolidate core runtime domains under `sdk`.
- Preserve compatibility for public imports and command behavior.

### Scope Clarification

- Phase 3 owns top-level domain movement and import-path consolidation.
- Phase 2 may include CLI package decomposition (`src/planpilot/cli.py` -> `src/planpilot/cli/`) as maintainability work.
- Phase 3 focuses on consolidating core runtime modules under `src/planpilot/sdk/` and finalizing root-domain import-path consolidation.

### Requirements

1. **Top-level domain shape**
   - `src/planpilot/cli/` remains the CLI entry domain.
   - Core runtime modules move under `src/planpilot/sdk/` (for example: contracts, engine, providers, plan, config, init, map_sync, clean).

2. **Compatibility strategy**
   - Preserve user-facing APIs exposed from `planpilot.__init__`.
   - Provide compatibility shims where needed during migration to avoid abrupt breakage.

3. **SDK ownership review task**
   - Review each planned SDK workflow/support module (for example: `sync_ops`, `map_sync_ops`, `clean_ops`, `persistence`) and explicitly decide whether its logic belongs in SDK composition/workflow orchestration or should live in a deeper domain module.
   - Record and apply the decision before finalizing the `sdk/` package layout to avoid reintroducing SDK scope drift.

4. **Behavioral safety**
   - No change to command flags, summaries, exit codes, or sync semantics.
   - No change to provider behavior or generated GraphQL client usage.

5. **Verification**
   - Must pass `poetry run poe check`.
   - Must pass boundary tests and targeted CLI/SDK/provider test suites.

### Deliverables

- New consolidated package layout centered on `cli` and `sdk`.
- Updated imports and compatibility shims with no user-visible behavior changes.
- Guardrail tests ensuring layering remains enforced after re-rooting.

### Exit Criteria

- Core modules are namespaced under `sdk`.
- Public API and runtime behavior remain stable.
- Quality and boundary gates are green.

## Phase 4 - Documentation Alignment and Completeness

### Motivation

Docs should describe current behavior and structure, not historical intent. Documentation updates are most reliable after code movement settles.

### Goals

- Bring architecture and module docs in sync with the final refactored implementation.
- Fix stale examples/counters/references.
- Preserve docs as a trustworthy contributor guide.

### Requirements

1. **Architecture docs alignment**
   - Update layer/dependency statements to match enforced code boundaries.
   - Ensure module responsibilities are accurate.

2. **Module docs accuracy**
   - Update provider, SDK, CLI, and config docs where drift exists.
   - Correct operation counts, file paths, and behavior notes.

3. **README and contributor docs sanity pass**
   - Ensure onboarding, commands, and examples reflect current implementation.

4. **Verification**
   - Run a doc consistency pass against source files.
   - Validate links/references and remove stale claims.

### Deliverables

- Updated docs with accurate architecture and module references.
- Corrected examples and operational inventories.

### Exit Criteria

- Docs and code are consistent.
- Contributor path is clear and trustworthy.

## Sequencing Rationale

- **Phase 1 first**: fixes correctness of architecture contracts.
- **Phase 2 second**: reduces module density and improves maintainability.
- **Phase 3 third**: consolidates runtime namespace once decomposition is stable.
- **Phase 4 fourth**: updates docs after structure settles to avoid churn.

## Risks and Controls

- **Risk:** behavior regressions during internal movement.
  - **Control:** strict no-behavior-change principle in Phases 1-3 and full test/typing gates.

- **Risk:** new drift introduced during refactor.
  - **Control:** explicit boundary requirements and guardrail checks.

- **Risk:** docs become stale again.
  - **Control:** phase-gated doc updates after code stabilization and consistency checks.
