# gh-project-plan-sync

Sync plan artifacts (`epics.json`, `stories.json`, `tasks.json`) into GitHub Issues and GitHub Projects v2.

## v1 scope

- One-way sync: local plan files -> GitHub
- Idempotent reruns via markers and sync map
- Dry-run preview and explicit apply mode

See `docs/architecture/v1-scope.md` for full in/out-of-scope details.

## Requirements

- Python 3.10+
- `gh` CLI installed and authenticated
- GitHub token/scopes sufficient for repo and project operations (`repo`, `project`)

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Dry-run first:

```bash
.venv/bin/plan-gh-project-sync \
  --repo your-org/your-repo \
  --project-url https://github.com/orgs/your-org/projects/1 \
  --epics-path .plans/epics.json \
  --stories-path .plans/stories.json \
  --tasks-path .plans/tasks.json \
  --sync-path .plans/github-sync-map.json \
  --label codex \
  --status Backlog \
  --priority P1 \
  --iteration active \
  --size-field Size \
  --size-from-tshirt true \
  --dry-run
```

Apply changes:

```bash
.venv/bin/plan-gh-project-sync \
  --repo your-org/your-repo \
  --project-url https://github.com/orgs/your-org/projects/1 \
  --epics-path .plans/epics.json \
  --stories-path .plans/stories.json \
  --tasks-path .plans/tasks.json \
  --sync-path .plans/github-sync-map.json \
  --apply
```

## Multi-epic note

Current core sync path expects one epic per run. For multi-epic plans, slice per epic and run sequentially (helper flow documented in roadmap integration notes).

```bash
PYTHONPATH=src python3 tools/slice_epics_for_sync.py \
  --epics-path .plans/epics.json \
  --stories-path .plans/stories.json \
  --tasks-path .plans/tasks.json \
  --out-dir .plans/tmp
```

## Verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"
PYTHONPATH=src python3 -m plan_gh_project_sync --help
```

## Install Skill: roadmap-to-github-project

Skill source in this repo:
- `skills/roadmap-to-github-project/SKILL.md`
- `skills/roadmap-to-github-project/helpers/slice_epics_for_sync.py`

Human install (copy into your OpenCode skills directory):

```bash
mkdir -p ~/.config/opencode/skills/roadmap-to-github-project/helpers
cp skills/roadmap-to-github-project/SKILL.md ~/.config/opencode/skills/roadmap-to-github-project/SKILL.md
cp skills/roadmap-to-github-project/helpers/slice_epics_for_sync.py ~/.config/opencode/skills/roadmap-to-github-project/helpers/slice_epics_for_sync.py
```

LLM install/use instructions:
- Reference the skill by path: `~/.config/opencode/skills/roadmap-to-github-project/SKILL.md`.
- Ask the agent to use `roadmap-to-github-project` mode (`plan`, `sync`, or `full`) and provide required inputs (`roadmap_path` for `plan`; `repo`, `project_url`, and plans paths for `sync`).
- If syncing multiple epics, instruct the agent to run `helpers/slice_epics_for_sync.py` before `plan-gh-project-sync`.

## Docs

- `docs/architecture/v1-scope.md`
- `docs/cli-reference.md`
- `docs/schemas.md`
- `docs/migration.md`
