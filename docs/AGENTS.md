# DOCS KNOWLEDGE BASE

## OVERVIEW
Documentation hub for architecture decisions, module specs, operational workflows, and release/testing behavior.

## STRUCTURE
```text
docs/
|- README.md               # Docs index + locked v2 decisions
|- how-it-works.md         # End-to-end behavior and semantics
|- modules/                # Module-level specs (CLI/SDK/providers/etc.)
|- testing/                # Testing guides (E2E and verification)
|- reference/              # User-facing reference docs (schemas, contracts)
|- design/                 # Architecture and layer dependency rules
`- decisions/              # ADRs (codegen and related rationale)
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Architecture boundaries | `docs/design/architecture.md` | Layer rules and allowed dependencies |
| Sync semantics | `docs/how-it-works.md` | Discovery/idempotency/dry-run behavior |
| Provider design | `docs/modules/providers.md` | Provider contract, retries, extension path |
| GitHub adapter details | `docs/modules/github-provider.md` | Operations and implementation notes |
| Test strategy | `docs/testing/e2e.md` | Offline E2E scope + extension guidelines |
| Plan schema examples | `docs/reference/plan-schemas.md` | Input model shape and examples |
| Release mechanics | `RELEASE.md`, `.github/workflows/release.yml` | TestPyPI gate + publish pipeline |

## CONVENTIONS
- `docs/README.md` is the source-of-truth index for docs navigation and locked decisions.
- Module specs in `docs/modules/` should reflect runtime code boundaries in `src/planpilot/`.
- Behavioral contracts (exit codes, discovery semantics, dry-run semantics) are documented as user-visible guarantees.
- ADRs in `docs/decisions/` explain why, not implementation walk-throughs.

## ANTI-PATTERNS
- Do not document behavior that contradicts runtime code or tests.
- Do not duplicate root README onboarding content inside module specs.
- Do not treat generated GraphQL client files as hand-edited architecture references.
- Do not add workflows/release guidance that bypasses semantic-release and CI gates.
