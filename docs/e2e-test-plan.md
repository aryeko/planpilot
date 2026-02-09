# Offline E2E Test Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add deterministic end-to-end coverage for CLI + SDK flows without network access.

**Architecture:** Drive E2E through real CLI/SDK boundaries with file-based fixtures and fake/dry-run providers. Validate behavior via exit codes, rendered summaries, sync-map outputs, and provider operation logs.

**Tech Stack:** Python 3.11+, pytest, pytest-asyncio, tempfile/pathlib, PlanPilot CLI (`planpilot sync`), `DryRunProvider` + fakes.

---

## Scope decisions (locked)

1. **DryRunProvider call logging is required** for deterministic verification.
2. **`provider: dry-run` is used to test apply-mode flow offline** (non-`--dry-run` path).
3. **Both plan input modes are mandatory** in E2E (`unified` and split `epics/stories/tasks`).

---

## Test layout

- Create: `tests/e2e/__init__.py`
- Create: `tests/e2e/test_cli_e2e.py`
- Create: `tests/e2e/fixtures/config/`
- Create: `tests/e2e/fixtures/plans/unified/`
- Create: `tests/e2e/fixtures/plans/split/`

Optional helpers:
- `tests/e2e/helpers.py` for fixture writing/process wrapper helpers.

---

## Required E2E cases

### Case 1: dry-run happy path (split input)

**Intent:** Validate full CLI dry-run mode with split files.

- Config uses GitHub provider shape but run uses dry-run mode.
- Command: `planpilot sync --config <cfg> --dry-run`
- Assert:
  - exit code `0`
  - summary contains mode `(dry-run)`
  - dry-run sync map exists at `<sync_path>.dry-run`
  - apply sync map path is not written

### Case 2: apply happy path via `provider=dry-run` (split input)

**Intent:** Validate non-dry-run engine path without network.

- Config: `provider: "dry-run"`
- Command: `planpilot sync --config <cfg> --apply`
- Assert:
  - exit code `0`
  - apply sync map written at `sync_path`
  - summary has `(apply)`
  - no network/auth dependency

### Case 3: unified input happy path

**Intent:** Ensure unified plan mode works end-to-end.

- Config uses `plan_paths.unified`
- Command: run both dry-run and apply(dry-run provider)
- Assert:
  - both exit `0`
  - deterministic counts/rows in summary

### Case 4: idempotent rerun (apply via dry-run provider)

**Intent:** Ensure second run does not duplicate items.

- Run apply twice with same plan/config
- Assert on run #2:
  - created counts are zero or unchanged according to provider semantics
  - entries remain stable (same item IDs/keys/urls)

### Case 5: update without duplication

**Intent:** Plan content changes should update existing mapping.

- First apply with baseline plan
- Modify title/body-relevant fields
- Second apply
- Assert same plan item IDs map to same provider keys, no new duplicates

### Case 6: validation failure (strict mode) -> exit 3

**Intent:** Broken references fail before provider mutation.

- Invalid plan fixture (`parent_id`/`depends_on` unresolved)
- Command: apply or dry-run
- Assert:
  - exit code `3`
  - stderr includes `error:` and validation context

### Case 7: provider/auth failures -> exit 4

**Intent:** Confirm provider/auth failure mapping.

- Fixture/provider monkeypatch that raises auth/provider error
- Assert exit `4`

### Case 8: sync failure -> exit 5

**Intent:** Confirm sync/reconciliation failure mapping.

- Force `SyncError` in execution path
- Assert exit `5`

### Case 9: unexpected failure -> exit 1

**Intent:** Defensive fallback mapping.

- Raise generic `RuntimeError`
- Assert exit `1`

### Case 10: usage failure -> exit 2

**Intent:** Argparse contract.

- Missing required args or no mode
- Assert `SystemExit(2)` behavior

### Case 11: summary contract stability

**Intent:** Verify user-facing output contract.

- Assert required blocks in order:
  - header/mode
  - plan metadata lines
  - created/existing counts
  - item table rows sorted deterministically
  - sync map line and dry-run note rules

### Case 12: sync-map contract

**Intent:** Validate persisted JSON schema + file location behavior.

- Assert fields: `plan_id`, `target`, `board_url`, `entries[*]` with expected item_type/key/url
- Assert suffix rule `.dry-run` in dry-run mode

---

## DryRunProvider instrumentation requirements

Add/keep a deterministic operation log in `DryRunProvider` (or test-only wrapper):

- operation name (`search_items`, `create_item`, `update_item`, `set_parent`, `add_dependency`)
- logical item id/key
- minimal payload fingerprint
- monotonic sequence index

E2E assertions should verify:

- expected operations were called
- sequence is correct for pipeline phase ordering
- no unexpected mutation operations in `--dry-run`

---

## Fixture matrix

Minimum fixture sets:

- `valid_split_small`
- `valid_unified_small`
- `invalid_strict_missing_parent`
- `invalid_strict_missing_dependency`
- `update_variant` (same IDs, changed content)

Config fixtures:

- `github_split_config`
- `dry_run_provider_split_config`
- `dry_run_provider_unified_config`

---

## Verification commands

- Focused E2E: `pytest -v tests/e2e/test_cli_e2e.py`
- Full suite: `poetry run poe check`

Expected gate:

- All new E2E pass deterministically offline
- No real network/API calls
- Exit code mapping and file outputs match docs
