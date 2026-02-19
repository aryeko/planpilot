# Example: Sync Workflow

A complete working example of a planpilot plan for a **User Authentication** epic with two stories and three tasks. Demonstrates the `planpilot sync` command.

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
planpilot sync --config examples/sync-workflow/planpilot.json --dry-run
```

### Apply (create issues)

```bash
planpilot sync --config examples/sync-workflow/planpilot.json --apply
```

Use any supported auth mode from config (`gh-cli`, `env`, or `token`).

## Sample output

### CLI output

[`dry-run-output.txt`](dry-run-output.txt) — the terminal output from a dry-run:

```text
planpilot - sync complete (dry-run)

  Plan ID:   3832d3ffce22
  Target:    example-org/example-repo
  Board:     https://github.com/orgs/example-org/projects/1

  Items:     6 total (1 epic, 2 stories, 3 tasks)
  Created:   6 (1 epic, 2 stories, 3 tasks)

  Sync map:  /absolute/path/to/examples/sync-map-sample.json.dry-run

  [dry-run] No changes were made
```

### Sync map

[`sync-map-sample.json`](sync-map-sample.json) — maps plan entity IDs to their GitHub issue metadata, used for idempotency on subsequent runs.

## What `--apply` creates on GitHub

1. **6 GitHub Issues** — 1 epic, 2 stories, 3 tasks, with type assignment based on `create_type_strategy`
2. **Sub-issue hierarchy** — stories linked under the epic, tasks under their stories
3. **Blocked-by relations** — T-2 and T-3 blocked by T-1, S-2 blocked by S-1 (roll-up)
4. **Project board items** — all issues added to the project with status, priority, iteration, and size fields set
5. **Cross-referenced bodies** — every issue body includes checklists and links to related issues
