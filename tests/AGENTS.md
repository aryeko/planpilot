# TEST SUITE KNOWLEDGE BASE

## OVERVIEW
Offline-first test suite mirroring runtime domains (`auth`, `contracts`, `engine`, `plan`, `providers`, `renderers`) plus CLI-focused E2E tests.

## STRUCTURE
```text
tests/
|- auth/                   # Token resolver and auth factory behavior
|- contracts/              # Core type/model validation and errors
|- engine/                 # Sync orchestration behavior and edge cases
|- plan/                   # Loader/validator/hasher behavior
|- providers/github/       # GitHub adapter behavior with fakes/mocks
|- renderers/              # Markdown rendering output contracts
|- e2e/                    # Offline CLI flow tests
`- fakes/                  # In-memory provider/renderer test doubles
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| End-to-end CLI behavior | `tests/e2e/test_cli_e2e.py` | Calls real CLI entrypoint without live network |
| Engine correctness | `tests/engine/test_engine.py` | discovery/upsert/enrich/relations coverage |
| SDK lifecycle/errors | `tests/test_sdk.py` | provider enter/exit and failure paths |
| GitHub adapter behavior | `tests/providers/github/test_provider.py` | provider CRUD/context behaviors |
| Shared fixtures | `tests/conftest.py` | sample plan/config fixtures |

## CONVENTIONS
- Keep tests offline; use mocks/fakes instead of live GitHub API calls.
- Mirror runtime module layout to keep ownership clear.
- Prefer behavior assertions over internal implementation details.
- Keep E2E deterministic by invoking `planpilot.cli.main()` directly.

## ANTI-PATTERNS
- Do not introduce real network/token dependencies in test paths.
- Do not couple tests to generated GraphQL client internals.
- Do not make E2E tests shell-dependent when direct Python entrypoints are available.
