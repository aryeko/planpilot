# Examples

Working examples demonstrating planpilot workflows.

| Example | Description |
|---------|-------------|
| [`sync-workflow/`](sync-workflow/) | Plan files + sync dry-run for a User Authentication epic (6 items) |
| [`full-workflow/`](full-workflow/) | Complete skill chain: idea → PRD → tech spec → plans JSON (20 items) |

## Quick start

### Sync workflow

```bash
planpilot sync --config examples/sync-workflow/planpilot.json --dry-run
```

### Full workflow

The [`full-workflow/`](full-workflow/) directory contains pre-generated artifacts from running the three planpilot skills in sequence:

1. **`create-prd`** — generate a PRD from a feature idea
2. **`create-tech-spec`** — generate a codebase-aware tech spec from the PRD
3. **`plan-sync`** — decompose the spec into epics, stories, and tasks

See each subdirectory's README for details.
