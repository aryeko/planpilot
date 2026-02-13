# Docs Coverage and IA Execution Plan (2026-02-13)

## Goal

Refresh documentation so it is easier to navigate end-to-end and better aligned with repository operations (code, tests, workflows, and release pipeline).

## Findings From Full-Repo Review

1. Docs are strong on architecture/module details, but workflow/testing/config operational docs are split across `README.md`, `RELEASE.md`, and workflow YAML with no single reference page.
2. There is no dedicated contributor-oriented verification runbook in docs reference pages.
3. Root and docs index pages do not explicitly surface CI/security/release workflow topology.
4. Local docs integrity checks were previously manual (fixed in this branch via CI + `docs-links` task), and docs should now reflect that command.

## Information Architecture Updates

- Keep current top-level structure under `docs/` (Design, Modules, Reference, Guides, Testing, Decisions, Plans).
- Expand **Reference** to include:
  - workflow automation reference
  - contributor verification reference
- Keep **Design** for architecture/ownership rules only.
- Keep **Plans** as historical execution artifacts.

## File Action Matrix

### Create

- `docs/reference/workflows-reference.md` — CI/release/security/codeql workflow behavior and guardrails.
- `docs/reference/developer-workflow.md` — canonical local verification checklist and command matrix.

### Update

- `README.md` — improve docs navigation + contributor verification command list.
- `docs/README.md` — add new reference docs and navigation path.
- `docs/design/documentation-architecture.md` — clarify ownership map and docs lifecycle.
- `RELEASE.md` — include docs validation commands in pre-release checks.
- `CONTRIBUTING.md` — align local pre-PR checks with current command set.

### Keep As-Is

- `docs/design/architecture.md`, `docs/design/engine.md`, `docs/design/contracts.md`, `docs/modules/*`, and ADR files remain structurally correct for current runtime.

## Mermaid Diagrams To Add

1. **Workflow Topology Diagram** in `docs/reference/workflows-reference.md`
   - Show CI -> Release gate and independent security lanes.
2. **Contributor Verification Flow** in `docs/reference/developer-workflow.md`
   - Show local check sequence and escalation path.
3. **Docs Lifecycle Diagram** update in `docs/design/documentation-architecture.md`
   - Show trigger -> file selection -> verification -> publication path.

## Execution Checklist

- [ ] Create `docs/reference/workflows-reference.md`.
- [ ] Create `docs/reference/developer-workflow.md`.
- [ ] Update `docs/README.md` navigation.
- [ ] Update root `README.md` docs pointers.
- [ ] Update `docs/design/documentation-architecture.md` with lifecycle flow.
- [ ] Update `RELEASE.md` pre-release checks.
- [ ] Update `CONTRIBUTING.md` verification section.
- [ ] Run `poetry run poe docs-links` and `poetry run poe check`.
