# TEST SUITE GUIDE

## OVERVIEW
Pytest suite mirroring `src/planpilot` domains with heavy use of fixtures and provider mocking.

## STRUCTURE
```text
tests/
├── models/                 # model-level validation behavior
├── plan/                   # loader/validator/hash tests
├── providers/github/       # gh client/provider/mapper behavior via mocks
├── rendering/              # markdown + component formatting
├── sync/                   # orchestration and relation logic
├── conftest.py             # shared fixtures
└── test_cli.py             # CLI integration-level behavior
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Add fixture shared by domains | `tests/conftest.py` | Prefer reusable fixture over local duplication |
| Validate sync orchestration | `tests/sync/test_engine.py` | Covers dry-run/apply and failure cases |
| Validate provider GitHub calls | `tests/providers/github/` | Mocks subprocess/GraphQL interactions |
| Validate CLI semantics | `tests/test_cli.py` | Arg parsing, exit codes, run behavior |

## CONVENTIONS
- Mirror new source modules with matching test path under `tests/`.
- Use `pytest.mark.asyncio` for async entry points and provider/client tests.
- Keep tests offline: mock provider/client; no real GitHub auth/API traffic.

## ANTI-PATTERNS
- Do not add tests that require live `gh` authentication or network access.
- Do not collapse domain tests into monolithic files; preserve mirrored layout.
- Do not weaken assertions to snapshot broad outputs when specific behavior is testable.
