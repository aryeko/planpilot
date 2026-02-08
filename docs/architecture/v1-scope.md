# v1 Scope

## In Scope

- One-way synchronization from local plan artifacts (`epics.json`, `stories.json`, `tasks.json`) to GitHub Issues and Projects v2.
- Idempotent upsert behavior using issue body markers and sync-map output.
- Dry-run preview mode and explicit apply mode.
- Epic, story, and task hierarchy linking (sub-issues when available; fallback links otherwise).
- Task dependency rendering as blocked-by relations.

## Out of Scope

- Bidirectional sync from GitHub back into plan files.
- Destructive default operations (automatic delete/close on missing local tasks).
- Automatic creation of project field definitions/options.
- Non-GitHub providers.

## Safety Model

- Mutations require explicit `--apply`.
- Missing auth fails fast before any remote mutation attempt.
- Input plan files are validated before sync execution.
