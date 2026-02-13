# Map Sync Design

## Purpose

`map sync` reconciles local artifacts from provider metadata for one existing remote plan ID. It is intentionally non-destructive to provider state: no create/update/delete operations occur in provider APIs.

## High-Level Flow

```mermaid
flowchart TD
    A[Discover candidate PLAN_ID values] --> B{plan-id selected?}
    B -- explicit --> C[Use --plan-id value]
    B -- implicit single candidate --> D[Auto-select]
    B -- multiple + TTY --> E[Interactive selection]
    B -- multiple + non-TTY --> F[Fail with guidance]
    C --> G[Run SDK map_sync(plan_id)]
    D --> G
    E --> G
    G --> H[Reconcile discovered items]
    H --> I{--dry-run?}
    I -- yes --> J[Print summary only]
    I -- no --> K[Write sync-map + local plan files]
```

## Runtime Steps

1. Discover candidate remote plan IDs via `PlanPilot.discover_remote_plan_ids()`.
2. Resolve the selected plan ID:
   - explicit `--plan-id` wins
   - otherwise one candidate auto-selects
   - otherwise interactive selection (TTY only)
   - otherwise fail in non-interactive mode
3. Run `PlanPilot.map_sync(plan_id=..., dry_run=...)`.
4. Build reconciliation diff (`added`, `updated`, `removed`) and reconstructed `remote_plan_items`.
5. In CLI apply mode, persist local artifacts:
   - sync map JSON
   - plan files reconstructed from metadata/body sections

## Ownership Boundaries

- SDK map-sync path returns `MapSyncResult` only.
- CLI owns local persistence policy and file output.
- Provider remains read-only for this workflow.

## Failure Semantics

- Missing candidates: config/usage failure with remediation guidance.
- Multiple candidates in non-interactive mode without `--plan-id`: fail-fast.
- Provider/auth failures map to CLI exit code `4`.
- Reconciliation/sync failures map to CLI exit code `5`.

## Contracted Outputs

- A stable result object (`MapSyncResult`) for programmatic consumers.
- Human-oriented CLI summary for operators.
- Optional local artifact writes in apply mode only.
