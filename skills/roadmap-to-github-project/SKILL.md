---
name: roadmap-to-github-project
description: Use when a user has a roadmap markdown file and wants .plans artifacts generated and synced to GitHub Issues + a Projects v2 board in one guided flow.
---

# Roadmap to GitHub Project

## Overview

Use this skill for end-to-end planning operations: convert roadmap markdown into schema-aligned `.plans` files, validate integrity, then sync epics/stories/tasks to GitHub Issues and Projects v2 with idempotent reruns.

This skill merges plan generation and sync. It supports `plan`, `sync`, and `full` modes.

## Skill Invocation Gate (MANDATORY)

Before any action, list available skills and invoke all that apply. If installed and applicable, you MUST use them. Process skills take priority over implementation skills.

## When to Use

- User asks to turn roadmap/spec docs into `.plans` JSON artifacts
- User asks to push epics/stories/tasks into GitHub Project from `.plans`
- User asks for one-command planning + project sync workflow

Do **not** use when the user is asking to implement roadmap tasks.

## Inputs

Required for `plan` mode:
- `roadmap_path`

Required for `sync` mode:
- `repo` (`OWNER/REPO`)
- `project_url` (Projects v2 URL)
- `epics_path`, `stories_path`, `tasks_path`

Recommended defaults:
- `plans_dir=.plans`
- `sync_path=.plans/github-sync-map.json`
- `label=planpilot`
- `status=Backlog`
- `priority=P1`
- `iteration=active`
- `size_field=Size`
- T-shirt size mapping is enabled by default (disable with `--no-size-from-tshirt`)

## Outputs

Planning artifacts:
- `.plans/epics.json`
- `.plans/stories.json`
- `.plans/tasks.json`
- `.plans/dependency-graph.md`

Sync artifacts:
- `.plans/github-sync-map.json`

## Workflow

### 1) Mode select

If mode is not explicit, ask once:
1. Plan only
2. Sync only
3. Full (plan + sync)

Default recommendation: Full.

### 2) Plan generation (plan/full)

1. Parse roadmap markdown
2. Build normalized hierarchy: Epic -> Story -> Task
3. Enforce story = PR-sized deliverable
4. Write `.plans/epics.json`, `.plans/stories.json`, `.plans/tasks.json`, `.plans/dependency-graph.md`
5. Validate:
   - JSON syntax
   - Cross-file references (epic/story/task/dependencies)
   - Required fields exist per schema

Required schema style:
- Match `spec-to-plan` / `planpilot` expectations:
  - `epics.json`: `id,title,goal,spec_ref,story_ids` (+ optional fields)
  - `stories.json`: `id,epic_id,title,goal,spec_ref,task_ids` (+ optional fields)
  - `tasks.json`: `id,story_id,title,motivation,spec_ref,requirements,acceptance_criteria,verification,artifacts,depends_on`

### 3) Sync preflight (sync/full)

1. `gh auth status`
2. Confirm target repo and project URL
3. Confirm tool availability:
   - preferred: `planpilot` (installed via pip/poetry)
   - fallback: `python3 -m planpilot`

If auth fails, STOP and request login.

### 4) Multi-epic handling (sync/full)

- run `planpilot` directly with full `.plans/epics.json`, `.plans/stories.json`, `.plans/tasks.json`
- native multi-epic validation + sync is supported

### 5) Sync execution (sync/full)

Preferred command template:

```bash
planpilot \
  --repo <owner/repo> \
  --project-url <project-url> \
  --epics-path .plans/epics.json \
  --stories-path .plans/stories.json \
  --tasks-path .plans/tasks.json \
  --sync-path .plans/github-sync-map.json \
  --label planpilot \
  --status Backlog \
  --priority P1 \
  --iteration active \
  --size-field Size \
  --dry-run --verbose
```

Then rerun replacing `--dry-run` with `--apply`.

### 6) Post-sync verification

Must report:
- Epic issue URLs
- Count of synced stories/tasks per epic
- Any warnings/fallbacks
- Sync map artifact paths

Sync writes one canonical map: `.plans/github-sync-map.json`.

## Common Mistakes

- Generating `.plans` with fields missing required by sync tool
- Skipping dry-run
- Treating this as implementation workflow (it is planning/sync only)

## Verification Checklist

- `python3 -m json.tool .plans/epics.json`
- `python3 -m json.tool .plans/stories.json`
- `python3 -m json.tool .plans/tasks.json`
- `gh auth status`
- Dry-run succeeds
- Real sync succeeds
- `.plans/github-sync-map.json` exists and parses

## Completion Criteria

This skill run is complete when:
1. `.plans` artifacts are valid and internally consistent
2. Epic/story/task issues are created or updated in target repo
3. Project items are added when project access is available
4. Canonical sync map is written for idempotent reruns
