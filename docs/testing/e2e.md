# E2E Testing (Offline)

This document describes the end-to-end (E2E) test suite for PlanPilot v2: design goals, what is covered, how to run it, and how to extend it safely.

## Goals

The E2E suite validates real CLI + SDK behavior without real network/API calls.

Primary goals:

- Verify `planpilot sync` behavior across both execution modes (`--dry-run`, `--apply`).
- Verify both plan input layouts (`unified`, split `epics/stories/tasks`).
- Verify output contracts that users depend on:
  - exit codes
  - summary shape/order
  - sync-map persistence and schema
- Verify idempotency and update behavior across reruns.
- Keep tests deterministic and fully offline.

## Test design

E2E tests intentionally run through the real CLI entrypoint (`planpilot.cli.main`) and real SDK composition (`PlanPilot.from_config`).

Design choices:

- No subprocess shell wrappers: tests call `main([...])` directly for speed and deterministic assertions.
- No network calls:
  - `--dry-run` path uses `DryRunProvider` by design.
  - apply-path offline coverage uses `provider: "dry-run"` + static token auth in fixture config.
- Provider operation sequencing is verified through `DryRunProvider.operations` log.

## Suite layout

- Test module: `tests/e2e/test_cli_e2e.py`
- Fixtures:
  - `tests/e2e/fixtures/plans/split/`
  - `tests/e2e/fixtures/plans/unified/`
  - `tests/e2e/fixtures/plans/invalid/`

## Coverage map

Current E2E cases:

**Sync subcommand:**

1. Split input happy path (`--dry-run`).
2. Split input happy path (`--apply` with `provider: dry-run`).
3. Unified input happy path (`--dry-run` and `--apply`).
4. Apply rerun idempotency (no duplicate creation on second run).
5. Apply update variant behavior (same item mapping, updates applied).
6. Strict validation failures -> exit code `3`:
   - missing parent
   - missing dependency
7. Usage/argparse failure -> exit code `2`.
8. Provider pipeline operation ordering in apply path:
   - discovery (`search_items`) before creation
   - creation before enrichment updates
   - updates before relation mutations
9. Summary output contract checks (critical block ordering).
10. Sync-map contract checks for both dry-run and apply outputs.
11. Error mapping checks:
    - `ConfigError` -> `3`
    - `AuthenticationError` / `ProviderError` -> `4`
    - `SyncError` -> `5`
    - unexpected error -> `1`

**Init subcommand:**

12. `init --defaults` generates a valid, parseable config.
13. `init --defaults` refuses to overwrite existing files (exit code `2`).
14. `init --defaults` -> `sync --dry-run` round-trip (generated config feeds into sync).
15. Interactive wizard (split layout) produces valid config + stub plan files.
16. Interactive wizard (unified layout) produces valid config.
17. Interactive wizard -> `sync --dry-run` round-trip with real fixtures.
18. Interactive wizard with advanced options (validation mode, max concurrent).
19. Interactive wizard Ctrl+C abort -> exit code `2`, no file written.
20. Interactive overwrite declined -> exit code `2`, original file preserved.
21. Interactive overwrite accepted -> `sync --dry-run` round-trip.

## DryRunProvider instrumentation

`DryRunProvider` now records deterministic operation logs via `DryRunOperation`:

- `sequence` (monotonic)
- `name` (operation name)
- `item_id` (logical target)
- `payload` (minimal fingerprint)

This enables assertions on phase ordering without coupling tests to provider internals.

## How to run

Run only E2E:

```bash
poetry run poe test-e2e
```

Run provider instrumentation unit tests:

```bash
poetry run pytest -v tests/providers/test_dry_run.py
```

Run non-E2E suite:

```bash
poetry run pytest -v tests --ignore=tests/e2e
```

Run E2E coverage XML:

```bash
poetry run poe coverage-e2e
```

Run full project checks:

```bash
poetry run poe check
```

## Current baseline

As of 2026-02-09:

- `tests/e2e/test_cli_e2e.py`: 26 tests passing (16 sync + 10 init).
- Full suite: 287 tests passing.

Treat these numbers as a moving baseline; update this section when adding/removing cases.

## Extension guidelines

When adding E2E scenarios:

- Prefer new fixtures over in-test inline JSON blobs.
- Keep assertions on stable contracts (exit codes, persisted files, required summary sections).
- Avoid asserting incidental formatting details that are not contractual.
- Keep tests offline and deterministic; avoid real provider/auth/network dependencies.
- If testing apply idempotency, ensure provider state persists across reruns in the same test.

## Non-goals

- Real GitHub integration coverage (belongs to provider integration tests and CI workflows with proper credentials).
- Snapshot testing entire CLI output verbatim.

## Related docs

- `docs/how-it-works.md`
- `docs/modules/cli.md`
- `docs/modules/sdk.md`
