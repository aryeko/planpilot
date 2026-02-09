---
name: spec-to-planpilot-sync
description: Use when a user has one or more PRD/spec files and needs standalone guidance to convert them into planpilot JSON plans and sync or update GitHub Issues plus Projects v2.
---

# Spec to PlanPilot Sync

## Overview

This skill is standalone for environments where `planpilot` is installed from pip (no source tree required).

Goal: convert PRD/spec inputs into valid plan JSON, then sync/update GitHub with dry-run-first safety.

## Prerequisites

- Python 3.11+
- `planpilot` installed: `pip install planpilot`
- `gh` CLI installed and authenticated
- GitHub token/scopes: `repo`, `project`

## When to Use

- User asks to break PRD/spec into epics, stories, tasks.
- User asks to sync/update GitHub Issues and Projects v2 from that plan.
- User has multiple overlapping specs and needs one merged executable plan.

Do not use for implementing features.

## Required Outputs

- `.plans/epics.json`
- `.plans/stories.json`
- `.plans/tasks.json`
- `planpilot.json`
- Sync map artifacts:
  - dry-run: `<sync_path>.dry-run`
  - apply: `<sync_path>`

## Canonical Config (`planpilot.json`)

```json
{
  "provider": "github",
  "target": "OWNER/REPO",
  "board_url": "https://github.com/orgs/OWNER/projects/NUMBER",
  "plan_paths": {
    "epics": ".plans/epics.json",
    "stories": ".plans/stories.json",
    "tasks": ".plans/tasks.json"
  },
  "sync_path": ".plans/github-sync-map.json"
}
```

## Plan JSON Contract (Split Format)

All three files are JSON arrays.

Required fields for every item:
- `id` (string)
- `title` (string)
- `goal` (string)
- `requirements` (string array)
- `acceptance_criteria` (string array)

Hierarchy rules:
- Story item must set `parent_id` to an Epic `id`.
- Task item must set `parent_id` to a Story `id`.
- Epic items must not use `parent_id`.

Optional fields:
- `depends_on` (string array of existing IDs)
- `sub_item_ids` (string array)
- `estimate` (object): `{"tshirt":"S"}` or `{"hours":6}`
- `verification` (object): `{"commands":[],"ci_checks":[],"evidence":[],"manual_steps":[]}`
- `spec_ref` (object): `{"url":"...","section":"...","quote":"..."}`
- `scope` (object): `{"in_scope":[],"out_scope":[]}`

JSON must be strict:
- no comments
- no trailing commas

## CLI Reference

Only supported sync command pattern:

```bash
planpilot sync --config ./planpilot.json --dry-run
planpilot sync --config ./planpilot.json --apply
```

Flags:
- `--config <path>` required
- exactly one of `--dry-run` or `--apply` required
- optional `--verbose`

## Execution Flow

1. Choose mode:
- `plan` (generate/validate JSON only)
- `sync` (sync existing JSON)
- `full` (generate + sync)

2. Analyze PRD/spec files:
- extract outcomes, requirements, constraints, dependencies
- resolve conflicts and record assumptions

Default conflict policy if user gives none:
- stricter acceptance criteria wins
- if equally strict, newer spec wording wins

3. Generate `.plans/*.json`:
- Epic = strategic outcome
- Story = PR-sized deliverable
- Task = concrete executable unit

4. Validate syntax:

```bash
python3 -m json.tool .plans/epics.json >/dev/null
python3 -m json.tool .plans/stories.json >/dev/null
python3 -m json.tool .plans/tasks.json >/dev/null
```

5. Validate integrity:
- IDs globally unique across epics/stories/tasks
- all `parent_id` links exist and type-match
- all `depends_on` links exist

6. Preflight:

```bash
gh auth status
planpilot --version
```

7. Run sync:

```bash
planpilot sync --config ./planpilot.json --dry-run
planpilot sync --config ./planpilot.json --apply
```

8. Verify update behavior:
- sync command succeeded
- expected created/existing counts shown
- sync map files written at expected paths
- rerun dry-run shows no unexpected churn

## Programmatic API Reference

Use when user asks for API usage instead of shell:

```python
import asyncio
from planpilot import PlanPilot, load_config

async def run() -> None:
    config = load_config("planpilot.json")
    pp = await PlanPilot.from_config(config)
    await pp.sync(dry_run=True)
    await pp.sync(dry_run=False)

asyncio.run(run())
```

## Common Mistakes

- Stopping at analysis notes without generating `.plans/*.json`.
- Using invalid nested-field shorthand (for example `estimate: "M"`).
- Producing invalid hierarchy (task under epic, story without epic).
- Skipping dry-run before apply.
- Using old/nonexistent CLI flags.
- Returning pseudo-JSON with comments.

## Completion Criteria

1. `.plans/epics.json`, `.plans/stories.json`, `.plans/tasks.json` are valid and linked correctly.
2. `planpilot.json` is present and correct.
3. Dry-run succeeds.
4. Apply succeeds when requested.
5. Sync map output exists and rerun behavior is idempotent.
