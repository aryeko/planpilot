# Phase 4: CLI

**Layer:** L4 (CLI)
**Branch:** `v2/cli`
**Phase:** 4 (after SDK merges)
**Dependencies:** SDK public API only (`from planpilot import ...`)
**Design doc:** [`../docs/modules/cli.md`](../docs/modules/cli.md)

---

## Files to Create

| File | Contents |
|------|----------|
| `cli.py` | `build_parser()`, `main()`, `_run_sync()`, `_format_summary()` |
| `__main__.py` | `python -m planpilot` support |

---

## Command Structure

```text
planpilot [--version]
planpilot sync --config <path> (--dry-run | --apply) [--verbose]
```

---

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `--config` | `str` | Yes | Path to `planpilot.json` |
| `--dry-run` | flag | One of these | Preview mode |
| `--apply` | flag | | Apply mode |
| `--verbose`, `-v` | flag | No | Debug logging |

`--dry-run` / `--apply` are mutually exclusive and one is required.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `2` | Usage/argument parsing failure |
| `3` | Config or plan validation failure |
| `4` | Authentication/provider/network failure |
| `5` | Sync/reconciliation failure |
| `1` | Unexpected internal failure |

---

## Output Format

```text
planpilot - sync complete (apply)

  Plan ID:   a1b2c3d4e5f6
  Target:    owner/repo
  Board:     https://github.com/orgs/owner/projects/1

  Created:   2 epic(s), 5 story(s), 12 task(s)
  Existing:  0 epic(s), 1 story(s), 3 task(s)

  Epic   E1      #42    https://github.com/owner/repo/issues/42
  ...

  Sync map:  /abs/path/to/sync-map.json

  [dry-run] No changes were made
```

---

## Test Strategy

| Test File | Key Cases |
|-----------|-----------|
| `test_cli.py` | `--dry-run` / `--apply` mutually exclusive, missing `--config` -> exit 2, `--version` prints version, successful sync -> exit 0 + summary output, ConfigError -> exit 3, AuthenticationError -> exit 4, SyncError -> exit 5, `--verbose` enables debug logging, output format matches spec |
