# Clean Module Spec

The clean module (`core/clean/`) plans deletion order for planpilot-managed items and supports safe cleanup workflows.

## Responsibilities

- Build deletion order that prefers leaf-first removal.
- Use metadata parent relationships when plan structure is absent (`--all` mode).
- Tolerate cycles and unmapped parents while preserving deterministic output.

## Core component

| Component | Responsibility |
|---|---|
| `CleanDeletionPlanner` | Compute deterministic deletion ordering from item + metadata inputs |

## Runtime behavior

The SDK cleanup path uses planner output and executes pass-based deletion in apply mode:

1. Attempt deletion for remaining items.
2. Keep failures and retry only failed items.
3. Stop when no failures remain.
4. If no progress is made in a pass, raise first provider error.

## Guarantees

- Dry-run performs discovery/filtering only (no delete mutations).
- Ordering is deterministic for equivalent inputs.
- Failures are explicit when cleanup cannot progress.

## Related docs

- `docs/design/clean.md`
- `docs/modules/sdk.md`
- `docs/modules/cli.md`
