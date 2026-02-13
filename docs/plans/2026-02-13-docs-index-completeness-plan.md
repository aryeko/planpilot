# Docs Index Completeness Plan (2026-02-13)

## Objective

Close remaining docs discoverability gaps by ensuring the docs index explicitly surfaces all durable documentation entry points.

## Findings from fresh repo-wide review

- Code, tests, workflows, and configuration checks are green (`poe check`, `poe test-e2e`, `poe workflow-lint`, `poe docs-links`).
- `docs/README.md` links nearly all key docs, but one durable docs page (`docs/AGENTS.md`) is not discoverable from the index.
- There is no single reference page that inventories all current docs files by area and owner intent.

## Planned documentation changes

### Create

- `docs/reference/docs-inventory.md`
  - Canonical inventory of documentation files grouped by area.
  - Includes ownership intent and when to update each section.
  - Includes a Mermaid map for quick navigation.

### Update

- `docs/README.md`
  - Add `Docs Inventory` to quick references.
  - Add `Agent Context` (`docs/AGENTS.md`) under maintainers/internal references.
- `README.md`
  - Add `Docs Inventory` in root docs navigation for top-level discoverability.

## Information architecture organization

- Keep current top-level docs taxonomy (`design`, `modules`, `reference`, `guides`, `testing`, `decisions`, `plans`).
- Place the cross-cutting inventory under `docs/reference/` because it is a navigation contract, not design rationale.

## Mermaid diagrams to include

1. **Docs navigation map** in `docs/reference/docs-inventory.md`
   - Shows index -> design/modules/reference/guides/testing/decisions/plans/internal.
2. **No new architecture diagrams** required in design docs for this pass.

## Execution checklist

- [ ] Create `docs/reference/docs-inventory.md` with navigation diagram and grouped tables.
- [ ] Update `docs/README.md` with inventory and agent-context links.
- [ ] Update root `README.md` docs links.
- [ ] Run `poetry run poe docs-links`.
- [ ] Run `poetry run poe check`.
