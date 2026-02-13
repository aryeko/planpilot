# Full Repo Review + Docs Overhaul Plan (2026-02-13)

## Scope

This plan follows a full from-scratch audit of code, docs, workflows, tests, and configuration. It defines:

1. non-doc fixes to apply first,
2. docs pages to update/create,
3. docs organization changes,
4. Mermaid diagrams to add,
5. execution + verification checkpoints.

## Findings Snapshot

### Code/workflow findings to fix now

- GitHub search labels were not quoted in provider discovery queries (`search_items`), which can break labels with spaces/special characters.
- Docs had drift and duplication around:
  - provider capability language,
  - relation contract wording,
  - operation counts and file structure,
  - auth requirements in top-level guides,
  - docs navigation that mixed active docs with historical execution plans.

### Findings deferred (explicit)

- Full GHES board URL support remains out of scope for this pass (would require broader target/provider compatibility changes).
- Release workflow privilege-splitting is deferred pending a dedicated release-pipeline hardening pass.

## Execution Phases

### Phase 1 - Non-doc fixes (complete first)

- Update `src/planpilot/core/providers/github/provider.py` to quote/escape labels in GraphQL search query construction.
- Add regression coverage in `tests/providers/github/test_provider.py` for labels containing spaces and quotes.

### Phase 2 - Documentation architecture pass

#### Update (existing docs)

- `README.md`
  - Remove duplicate docs navigation blocks.
  - Clarify auth requirements (`gh` is required for `gh-cli` auth, optional for `env`/`token`).
  - Keep quickstart concise and point to reference pages.
- `docs/README.md`
  - Reorganize into: Start Here, References, Module Specs, Design, Operations, Archive/Plans.
  - Remove historical execution plan pages from primary "start here" list.
- `docs/modules/providers.md`
  - Align capability wording with current implementation behavior.
  - Tighten discovery and reconciliation guarantees to what code actually enforces.
- `docs/modules/github-provider.md`
  - Align startup/capability wording with code reality.
  - Ensure operations count, file tree, and strategy behavior match current source.
- `docs/design/contracts.md`
  - Correct `Item` contract narrative to include legacy relation methods as compatibility surface while positioning `reconcile_relations` as orchestration path.
- `docs/modules/config.md`
  - Clarify provider-specific URL constraints and auth behavior.
- `docs/reference/cli-reference.md`
  - Keep command surface canonical and reference shared exit-code page.
- `docs/reference/sdk-reference.md`
  - Keep ownership boundaries explicit and concise.
- `docs/decisions/001-ariadne-codegen.md`
  - Correct operation totals and keep rationale in sync with current repository.
- `docs/design/documentation-architecture.md`
  - Reflect updated docs IA and maintenance rules.
- `examples/README.md`
  - Clarify apply-mode auth wording and conditional type strategy behavior.
- `skills/INSTALL.md`
  - Replace mutable-branch self-install wording with safer pinned-release guidance.

#### Create (new docs)

- `docs/reference/config-reference.md`
  - Canonical field-by-field config reference with validation and examples.
- `docs/reference/exit-codes.md`
  - Single source of truth for CLI exit code mapping and examples.
- `docs/design/codemap.md`
  - Runtime package map and dependency boundaries tied to actual directory layout.

### Phase 3 - Mermaid diagram additions

- Add/update diagrams in:
  - `docs/README.md`: docs navigation map by audience/use-case.
  - `docs/modules/providers.md`: provider create-type strategy + fallback flow.
  - `docs/modules/github-provider.md`: create/update/reconcile operation flow.
  - `docs/reference/config-reference.md`: auth resolution decision flow.
  - `docs/reference/exit-codes.md`: exception-to-exit-code mapping flow.

## Docs Organization Target

Primary taxonomy after this pass:

- `docs/design/` - architecture, contracts, engine/workflow design, codemap.
- `docs/modules/` - implementation-facing module specs.
- `docs/reference/` - user/operator lookup docs (CLI/SDK/config/exit codes/schemas).
- `docs/guides/` - troubleshooting and task-oriented how-tos.
- `docs/testing/` - testing strategy and execution guidance.
- `docs/decisions/` - ADRs.
- `docs/plans/` - historical execution plans (explicitly labeled as archive artifacts).

## Verification Gates

Run after non-doc + docs execution:

1. `poetry run poe check`
2. `poetry run poe test-e2e`
3. `poetry build`

Then perform a final review pass and only push when clean.
