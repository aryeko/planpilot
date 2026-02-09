# Examples

This directory contains a complete working example of a planpilot plan for a **User Authentication** epic with two stories and three tasks.

## Plan files

| File | Description |
|------|-------------|
| [`epics.json`](epics.json) | 1 epic: User Authentication |
| [`stories.json`](stories.json) | 2 stories: User Registration, User Login and Sessions |
| [`tasks.json`](tasks.json) | 3 tasks: user model, registration endpoint, login endpoint |
| [`planpilot.json`](planpilot.json) | Config file pointing at the above plan files |

### Dependency graph

```text
E-1 User Authentication
├── S-1 User Registration
│   ├── T-1 Add user model and migration
│   └── T-2 Implement registration endpoint  (depends on T-1)
└── S-2 User Login and Sessions
    └── T-3 Implement login endpoint          (depends on T-1)
```

## Running

### Dry-run (preview, fully offline)

```bash
planpilot sync --config examples/planpilot.json --dry-run
```

### Apply (create issues, requires `gh` auth)

```bash
planpilot sync --config examples/planpilot.json --apply
```

To use these examples in your own repo, copy the `examples/` directory and update `planpilot.json` with your `target` and `board_url`.

## Sample output

The files below were produced by running `planpilot sync --dry-run` against the plan files in this directory.

### CLI output

[`dry-run-output.txt`](dry-run-output.txt) — the terminal output from a dry-run:

```text
planpilot - sync complete (dry-run)

  Plan ID:   3832d3ffce22
  Target:    example-org/example-repo
  Board:     https://github.com/orgs/example-org/projects/1

  Created:   1 epic(s), 2 story(s), 3 task(s)

  Epic   E-1     dry-run  dry-run
  Story  S-1     dry-run  dry-run
  Story  S-2     dry-run  dry-run
  Task   T-1     dry-run  dry-run
  Task   T-2     dry-run  dry-run
  Task   T-3     dry-run  dry-run

  Sync map:  examples/sync-map-sample.json.dry-run

  [dry-run] No changes were made
```

In dry-run mode, keys and URLs show `dry-run` since no GitHub issues are created. In `--apply` mode, these will be real issue numbers and URLs.

### Sync map

[`sync-map-sample.json`](sync-map-sample.json) — the sync map written by the dry-run. This file maps plan entity IDs to their GitHub issue metadata and is used for idempotency on subsequent runs.

## What `--apply` creates on GitHub

After running with `--apply`, planpilot creates:

1. **6 GitHub Issues** — 1 epic, 2 stories, 3 tasks, each with issue type set
2. **Sub-issue hierarchy** — stories linked under the epic, tasks under their stories
3. **Blocked-by relations** — T-2 and T-3 blocked by T-1, S-2 blocked by S-1 (roll-up)
4. **Project board items** — all issues added to the project with status, priority, iteration, and size fields set
5. **Cross-referenced bodies** — every issue body includes checklists and links to related issues
