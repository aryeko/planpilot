# CLI Reference

```bash
plan-gh-project-sync \
  --repo OWNER/REPO \
  --project-url https://github.com/orgs/<org>/projects/<num> \
  --epics-path .plans/epics.json \
  --stories-path .plans/stories.json \
  --tasks-path .plans/tasks.json \
  --sync-path .plans/github-sync-map.json \
  (--dry-run | --apply)
```

## Required flags

- `--repo`
- `--project-url`
- `--epics-path`
- `--stories-path`
- `--tasks-path`
- `--sync-path`
- One mode flag: `--dry-run` or `--apply`

## Optional flags

- `--label` (default `codex`)
- `--status` (default `Backlog`)
- `--priority` (default `P1`)
- `--iteration` (default `active`)
- `--size-field` (default `Size`)
- `--size-from-tshirt` (`true`/`false`)
- `--verbose`
