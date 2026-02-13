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

To generate your own config interactively, use `planpilot init` instead of creating `planpilot.json` by hand.

### Dry-run (preview, fully offline)

```bash
planpilot sync --config examples/planpilot.json --dry-run
```

### Apply (create issues)

```bash
planpilot sync --config examples/planpilot.json --apply
```

Use any supported auth mode from config (`gh-cli`, `env`, or `token`). `gh` CLI is only required when `auth` is `gh-cli`.

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

  Items:     6 total (1 epic, 2 stories, 3 tasks)
  Created:   6 (1 epic, 2 stories, 3 tasks)

  Sync map:  /absolute/path/to/examples/sync-map-sample.json.dry-run

  [dry-run] No changes were made
```

In dry-run mode, no GitHub issues are created and the sync map is written to `<sync_path>.dry-run`.

### Sync map

[`sync-map-sample.json`](sync-map-sample.json) — the sync map written by the dry-run. This file maps plan entity IDs to their GitHub issue metadata and is used for idempotency on subsequent runs.

## What `--apply` creates on GitHub

After running with `--apply`, planpilot creates:

1. **6 GitHub Issues** — 1 epic, 2 stories, 3 tasks, with type assignment based on `create_type_strategy` (issue type or labels)
2. **Sub-issue hierarchy** — stories linked under the epic, tasks under their stories
3. **Blocked-by relations** — T-2 and T-3 blocked by T-1, S-2 blocked by S-1 (roll-up)
4. **Project board items** — all issues added to the project with status, priority, iteration, and size fields set
5. **Cross-referenced bodies** — every issue body includes checklists and links to related issues
