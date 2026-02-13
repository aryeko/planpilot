# CLI Reference

## Commands

| Command | Purpose |
|---|---|
| `planpilot init` | Generate `planpilot.json` (interactive or defaults) |
| `planpilot sync` | Sync local plan files to provider |
| `planpilot map sync` | Reconcile local artifacts from remote metadata |
| `planpilot clean` | Delete planpilot-managed items (scoped or all-plans) |

## `planpilot init`

| Flag | Default | Description |
|---|---|---|
| `--output`, `-o` | `planpilot.json` | Output file path |
| `--defaults` | off | Non-interactive config generation |

## `planpilot sync`

| Flag | Default | Description |
|---|---|---|
| `--config` | `./planpilot.json` | Config path |
| `--dry-run` | required mode | Preview mode (no provider mutations) |
| `--apply` | required mode | Apply mode |
| `--verbose`, `-v` | off | Debug logging |

## `planpilot map sync`

| Flag | Default | Description |
|---|---|---|
| `--config` | `./planpilot.json` | Config path |
| `--dry-run` | required mode | Preview reconciliation only |
| `--apply` | required mode | Persist reconciled local artifacts |
| `--plan-id` | auto | Explicit remote plan ID |
| `--verbose`, `-v` | off | Debug logging |

Notes:
- No provider items are created/updated/deleted in `map sync`.
- In apply mode, CLI writes local sync-map and local plan files.

## `planpilot clean`

| Flag | Default | Description |
|---|---|---|
| `--config` | `./planpilot.json` | Config path |
| `--dry-run` | required mode | Preview deletions only |
| `--apply` | required mode | Execute deletions |
| `--all` | off | Target all planpilot-managed items by label |
| `--verbose`, `-v` | off | Debug logging |

## Exit codes

See [Exit Codes](./exit-codes.md) for the canonical mapping and exception flow.
