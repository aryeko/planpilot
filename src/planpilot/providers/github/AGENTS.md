# GITHUB PROVIDER KNOWLEDGE BASE

## OVERVIEW
GitHub adapter layer: project/repo context resolution, issue CRUD, relations, and generated GraphQL client integration.

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Main adapter behavior | `src/planpilot/providers/github/provider.py` | `GitHubProvider` context manager + provider contract methods |
| Item wrapper behavior | `src/planpilot/providers/github/item.py` | `Item` implementation for relations |
| URL/field mapping | `src/planpilot/providers/github/mapper.py` | project URL parsing + option resolution |
| Provider context models | `src/planpilot/providers/github/models.py` | resolved field/context state |
| GraphQL operations source | `src/planpilot/providers/github/operations/` | `.graphql` operation definitions |
| Generated typed client | `src/planpilot/core/providers/github/github_gql/` | ariadne-codegen output |

## CONVENTIONS
- Keep `provider.py` as a thin adapter over generated client methods.
- Add/modify GraphQL queries in `operations/`; regenerate client instead of manual client edits.
- Preserve idempotent behavior in create/update flows (`_ensure_*` helpers).
- Keep capability gates explicit (`supports_sub_issues`, `supports_blocked_by`, etc.).

## ANTI-PATTERNS
- Do not hand-edit files under `src/planpilot/core/providers/github/github_gql/` as primary change path.
- Do not add raw GraphQL string literals directly in `provider.py`.
- Do not leak GitHub-specific exceptions outside provider boundary without mapping.
- Do not skip context resolution in `__aenter__`; provider methods rely on populated `self.context`.

## NOTES
- `gen-client` task regenerates `github_gql` and applies Ruff fix/format.
- Mypy excludes generated client; keep strict typing in non-generated provider code.
