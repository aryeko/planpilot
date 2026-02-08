# GITHUB PROVIDER GUIDE

## OVERVIEW
GitHub-specific provider implementation backed by `gh` CLI and GraphQL queries.

## STRUCTURE
```text
src/planpilot/providers/github/
├── client.py     # Async `gh` subprocess wrapper
├── mapper.py     # Parse/mapping helpers (markers, URLs, options)
├── provider.py   # Provider ABC implementation
└── queries.py    # GraphQL query/mutation constants
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Add/change GraphQL operations | `src/planpilot/providers/github/queries.py` | Keep query constants centralized |
| Change API call execution | `src/planpilot/providers/github/client.py` | Async subprocess wrapper + error handling |
| Map API responses | `src/planpilot/providers/github/mapper.py` | Parse markers, options, project URLs |
| Provider behavior | `src/planpilot/providers/github/provider.py` | Implements `Provider` ABC end-to-end |

## CONVENTIONS
- `provider.py` owns workflow logic; `client.py` owns command execution.
- Use mapper helpers for parsing/transformations instead of inline duplication.
- Prefer resilient handling for optional project fields/iteration resolution.
- Keep issue relation fetches batched (current implementation chunks IDs).

## ANTI-PATTERNS
- Do not hardcode repository/project IDs in code paths.
- Do not let raw `gh` failures leak; wrap/translate to `ProviderError`/domain errors.
- Do not spread GraphQL query strings across files; keep them in `queries.py`.
- Do not make network calls in tests for this module; mock `GhClient`.

## NOTES
- Project item lookups and issue relation queries are pagination/batch sensitive.
- Label creation fallback exists in `provider.py`; keep it idempotent and failure-tolerant.
