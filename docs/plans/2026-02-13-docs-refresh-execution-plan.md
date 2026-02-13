# Docs Refresh Execution Plan (2026-02-13)

## Objective

Run a full docs-system pass after repo-wide review, then execute targeted updates so docs match runtime behavior, workflow policy, and current test/config baselines.

## Findings Snapshot

1. Contracts/architecture docs still describe relation calls as `set_parent` / `add_dependency`, while runtime now uses reconciliation (`reconcile_relations`).
2. GitHub provider docs have stale operation inventory details.
3. E2E baseline count in docs is stale.
4. Docs navigation is deep but not task-oriented (missing concise CLI/SDK reference and troubleshooting guides).
5. Existing plan artifact status block is stale and should be marked historical.

## Documentation Inventory and Actions

| Path | Action | Why |
|---|---|---|
| `README.md` | Update | Improve docs navigation and reference links |
| `CONTRIBUTING.md` | Update | Align contributor guidance with docs governance + workflow lint task |
| `RELEASE.md` | Keep | Release semantics unchanged in this docs pass |
| `docs/README.md` | Update | Add task-oriented structure and links to new docs |
| `docs/AGENTS.md` | Keep | Internal docs-agent guidance still accurate |
| `docs/how-it-works.md` | Keep | Behavior remains accurate after current changes |
| `docs/design/architecture.md` | Update | Reflect relation reconciliation model and correct layer wording |
| `docs/design/contracts.md` | Update | Add `reconcile_relations` contract details |
| `docs/design/engine.md` | Update | Clarify Phase 4 reconciliation behavior and flow |
| `docs/design/map-sync.md` | Keep | Flow and semantics remain accurate |
| `docs/design/clean.md` | Keep | Flow and semantics remain accurate |
| `docs/design/repository-layout.md` | Keep | Ownership map remains accurate |
| `docs/design/documentation-architecture.md` | Keep | Recently updated with decision flow |
| `docs/modules/cli.md` | Update | Link to new CLI reference and troubleshooting |
| `docs/modules/sdk.md` | Update | Link to new SDK reference and tighten persistence wording |
| `docs/modules/providers.md` | Update | Reconcile relation-method language |
| `docs/modules/github-provider.md` | Update | Fix operation/file inventory and relation API wording |
| `docs/modules/plan.md` | Keep | No drift found |
| `docs/modules/config.md` | Keep | No drift found |
| `docs/modules/auth.md` | Update | Add init auth preflight sequence diagram |
| `docs/modules/renderers.md` | Keep | No drift found |
| `docs/reference/plan-schemas.md` | Keep | No drift found |
| `docs/testing/e2e.md` | Update | Refresh baseline section |
| `docs/decisions/001-ariadne-codegen.md` | Update | Correct operation count in context |
| `docs/plans/2026-02-13-repo-review-and-docs-plan.md` | Update | Mark historical and superseded by this plan |

## New Docs To Create

1. `docs/reference/cli-reference.md` - concise command/flag matrix with examples.
2. `docs/reference/sdk-reference.md` - concise API reference for SDK entrypoints and result types.
3. `docs/guides/troubleshooting.md` - practical failure -> fix runbook.
4. `docs/modules/map-sync.md` - module-level behavior spec for `core/map_sync/*`.
5. `docs/modules/clean.md` - module-level behavior spec for `core/clean/*`.

## Organization Updates

- Keep existing `design/`, `modules/`, `reference/`, `testing/`, `plans/` layout.
- Add `guides/` for operator runbooks and troubleshooting.
- Move quick command/API lookup to `reference/` to avoid overloading module docs.

## Mermaid Diagram Additions

1. `docs/modules/auth.md` - init auth preflight sequence (`target -> token -> probes -> owner-type`).
2. `docs/design/engine.md` - relation reconciliation flow (`desired -> current -> remove stale -> add missing`).
3. `docs/README.md` - docs navigation flow (`start -> module -> reference -> deep design`).

## Execution Checklist

- [x] Plan created
- [x] Create new docs files
- [x] Update existing docs and root README/CONTRIBUTING references
- [ ] Validate links and run full verification (`poe check`, `poe test-e2e`, `poetry build`)
- [ ] Commit docs refresh
