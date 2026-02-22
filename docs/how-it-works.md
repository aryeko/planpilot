# How It Works

## Overview

`planpilot` reads plan JSON, validates it, discovers existing provider items by metadata marker, then creates/updates items and relations. Runs are idempotent by design.

## Sync flow

1. Load config from `planpilot.json`.
2. Load plan files (`unified` or `epics/stories/tasks`).
3. Validate plan structure and references (`strict` or `partial` mode).
4. Compute deterministic `plan_id`.
5. Discover existing items by metadata (`PLAN_ID:<plan_id>` marker).
6. Upsert missing/changed items.
7. Enrich bodies with context links/checklists.
8. Apply relations (parent/dependency) when supported by provider.
9. Persist sync map (`sync_path` for apply, `sync_path.dry-run` for dry-run) in CLI flows.

```mermaid
flowchart TD
    A[Load config] --> B[Load plan files]
    B --> C[Validate plan]
    C --> D[Compute plan_id]
    D --> E[Discover existing items by metadata]
    E --> F[Upsert items]
    F --> G[Enrich rendered bodies]
    G --> H[Apply relations]
    H --> I[Persist sync artifacts]
```

## Clean flow

`planpilot clean` discovers and deletes planpilot-managed provider issues. It always uses the real provider for discovery so previews are accurate.

1. Load config from `planpilot.json`.
2. Compute `plan_id` from local plan files (default mode) or skip (with `--all`).
3. Discover provider issues by metadata marker (`PLANPILOT_META_V1` block in issue body).
4. Filter: default targets current `plan_id` only; `--all` targets every planpilot-managed issue.
5. Order deletions leaf-first (tasks → stories → epics) to avoid dangling sub-issues.
6. Delete each issue, or preview in dry-run mode.

```mermaid
flowchart TD
    A[Load config] --> C{--all flag?}
    C -- No --> B[Compute plan_id]
    B --> D[Discover issues matching plan_id]
    C -- Yes --> E[Discover all planpilot-managed issues]
    D --> F[Order deletions leaf-first]
    E --> F
    F --> G{dry-run?}
    G -- Yes --> H[Print deletion preview]
    G -- No --> I[Delete issues]
```

See [design/clean.md](design/clean.md) and [modules/clean.md](modules/clean.md) for implementation details.

## Map sync flow

`planpilot map sync` reconciles the local `sync-map.json` from provider metadata without mutating any provider items. Use it to recover or bootstrap local artifacts when they are missing or out of sync.

1. Load config from `planpilot.json`.
2. Discover remote plan IDs from provider metadata (or use explicit `--plan-id`).
3. If no candidates: fail with an error (run `planpilot sync` first, or pass `--plan-id` to target a known plan). If multiple candidates and interactive TTY: prompt to select; otherwise fail.
4. Fetch item metadata/bodies for the selected plan.
5. Reconcile: match provider items to local plan entries.
6. In dry-run: print reconciliation preview. In apply: write local `sync-map.json` and plan files.

```mermaid
flowchart TD
    A[Load config] --> B{--plan-id provided?}
    B -- Yes --> D[Use explicit plan_id]
    B -- No --> C[Discover remote plan IDs from metadata]
    C --> E{How many candidates?}
    E -- Zero --> M[Fail: no managed issues found]
    E -- One --> D
    E -- Multiple + TTY --> F[Prompt user to select]
    E -- Multiple + no TTY --> G[Fail: require --plan-id]
    F --> D
    D --> H[Fetch item metadata for plan]
    H --> I[Reconcile provider items to local entries]
    I --> J{dry-run?}
    J -- Yes --> K[Print reconciliation preview]
    J -- No --> L[Write sync-map.json + plan files]
```

See [design/map-sync.md](design/map-sync.md) and [modules/map-sync.md](modules/map-sync.md) for implementation details.

## Idempotency model

- Each rendered body includes:
  - `PLANPILOT_META_V1`
  - `PLAN_ID:<id>`
  - `ITEM_ID:<id>`
  - `ITEM_TYPE:<EPIC|STORY|TASK>`
  - `PARENT_ID:<id or empty>`
  - `END_PLANPILOT_META`
- Discovery matches these markers, so reruns update the same provider items instead of creating duplicates.

## Dry-run behavior

- `sync --dry-run` uses `DryRunProvider`:
  - no auth/network calls
  - no provider mutations
- A dry-run sync map is still written to `<sync_path>.dry-run` for inspection.
- `clean --dry-run` is discovery-only but still uses the real provider so deletion previews are accurate.

## Apply behavior

- `--apply` uses the configured provider.
- Create/update operations run through provider-level retries/rate-limit handling.
- Sync map is written to `sync_path`.

## Validation modes

- `strict`: all references (`parent_id`, `depends_on`) must resolve in loaded items.
- `partial`: unresolved references are allowed when referenced items are not included in this run.

## Output and exit codes

- CLI summary is human-focused.
- See [reference/exit-codes.md](reference/exit-codes.md) for canonical process-exit mapping.
