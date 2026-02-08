# CLI Reference

## planpilot

Sync plan artifacts to GitHub Issues and Projects v2.

```bash
planpilot \
  --repo OWNER/REPO \
  --project-url https://github.com/orgs/<org>/projects/<num> \
  --epics-path .plans/epics.json \
  --stories-path .plans/stories.json \
  --tasks-path .plans/tasks.json \
  --sync-path .plans/github-sync-map.json \
  (--dry-run | --apply)
```

### Required flags

- `--repo` -- GitHub repository (OWNER/REPO)
- `--project-url` -- GitHub Projects v2 URL
- `--epics-path` -- Path to epics.json
- `--stories-path` -- Path to stories.json
- `--tasks-path` -- Path to tasks.json
- `--sync-path` -- Path to write sync map output
- One mode flag: `--dry-run` or `--apply`

### Optional flags

- `--label` (default `planpilot`) -- Label to apply to created issues
- `--status` (default `Backlog`) -- Project status option name
- `--priority` (default `P1`) -- Project priority option name
- `--iteration` (default `active`) -- Iteration title, or `active` / `none`
- `--size-field` (default `Size`) -- Project size field name (empty to skip)
- `--no-size-from-tshirt` -- Disable t-shirt size mapping (enabled by default)
- `--verbose`, `-v` -- Enable verbose logging

## planpilot-slice

Slice multi-epic plans into per-epic JSON files for sequential sync.

```bash
planpilot-slice \
  --epics-path .plans/epics.json \
  --stories-path .plans/stories.json \
  --tasks-path .plans/tasks.json \
  --out-dir .plans/tmp
```

### Flags

- `--epics-path` (required) -- Path to epics.json
- `--stories-path` (required) -- Path to stories.json
- `--tasks-path` (required) -- Path to tasks.json
- `--out-dir` (default `.plans/tmp`) -- Output directory for per-epic slices

## planpilot sync-all

Compatibility orchestration command for multi-epic plans. Prefer native `planpilot`
for direct multi-epic sync; use `sync-all` when you want explicit slice + per-epic
sync-map artifacts.

```bash
planpilot sync-all \
  --repo OWNER/REPO \
  --project-url https://github.com/orgs/<org>/projects/<num> \
  --epics-path .plans/epics.json \
  --stories-path .plans/stories.json \
  --tasks-path .plans/tasks.json \
  --sync-path .plans/github-sync-map.json \
  (--dry-run | --apply)
```

`sync-all` accepts the same optional flags as `planpilot`.
