# Examples

This directory contains a complete working example of a planpilot plan for a **User Authentication** epic with two stories and three tasks.

## Plan files

| File | Description |
|------|-------------|
| [`epics.json`](epics.json) | 1 epic: User Authentication |
| [`stories.json`](stories.json) | 2 stories: User Registration, User Login and Sessions |
| [`tasks.json`](tasks.json) | 3 tasks: user model, registration endpoint, login endpoint |

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

### Dry-run (preview)

```bash
planpilot \
  --repo your-org/your-repo \
  --project-url https://github.com/orgs/your-org/projects/1 \
  --epics-path examples/epics.json \
  --stories-path examples/stories.json \
  --tasks-path examples/tasks.json \
  --sync-path examples/sync-map.json \
  --dry-run --verbose
```

Expected output:

```text
[dry-run] No changes will be made
[dry-run] create epic: User Authentication
[dry-run] create story: User Registration
[dry-run] create story: User Login and Sessions
[dry-run] create task: Add user model and migration
[dry-run] create task: Implement registration endpoint
[dry-run] create task: Implement login endpoint with token generation
Sync complete (dry-run): 1 epics, 2 stories, 3 tasks
```

### Apply (create issues)

```bash
planpilot \
  --repo your-org/your-repo \
  --project-url https://github.com/orgs/your-org/projects/1 \
  --epics-path examples/epics.json \
  --stories-path examples/stories.json \
  --tasks-path examples/tasks.json \
  --sync-path examples/sync-map.json \
  --apply --verbose
```

## Sample output

### Sync map

After a successful `--apply` run, planpilot writes a `sync-map.json` file mapping plan IDs to GitHub issue numbers and node IDs. See [`sync-map-sample.json`](sync-map-sample.json) for an example.

The sync map is used for idempotency — subsequent runs detect existing issues and skip creation.

### Rendered issue bodies

The `output/` directory contains the Markdown bodies that planpilot generates for each issue after a full sync. These show the final state including cross-references (e.g. `#1`, `#2`) and checklists:

| File | Issue | Highlights |
|------|-------|------------|
| [`output/epic-E-1.md`](output/epic-E-1.md) | Epic: User Authentication | Stories checklist with issue links |
| [`output/story-S-1.md`](output/story-S-1.md) | Story: User Registration | Task checklist, epic back-ref |
| [`output/story-S-2.md`](output/story-S-2.md) | Story: User Login and Sessions | Task checklist, epic back-ref |
| [`output/task-T-1.md`](output/task-T-1.md) | Task: Add user model and migration | No dependencies |
| [`output/task-T-2.md`](output/task-T-2.md) | Task: Implement registration endpoint | Blocked by T-1 (`#4`) |
| [`output/task-T-3.md`](output/task-T-3.md) | Task: Implement login endpoint | Blocked by T-1 (`#4`) |

### What planpilot creates on GitHub

After `--apply`, you get:

1. **6 GitHub Issues** — 1 epic, 2 stories, 3 tasks, each with issue type set
2. **Sub-issue hierarchy** — stories linked under the epic, tasks under their stories
3. **Blocked-by relations** — T-2 and T-3 blocked by T-1, S-2 blocked by S-1 (roll-up)
4. **Project board items** — all issues added to the project with status, priority, iteration, and size fields set
5. **Cross-referenced bodies** — every issue body includes checklists and links to related issues
