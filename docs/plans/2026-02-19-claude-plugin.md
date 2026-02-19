# Claude Code Plugin Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Package planpilot's three skills as a Claude Code plugin with slash commands, distributed via the planpilot GitHub repo as a self-hosted marketplace.

**Architecture:** Add `.claude-plugin/plugin.json` to the repo root (Approach A — repo IS the marketplace). Rename `skills/roadmap-to-github-project/` → `skills/plan-sync/` and update all cross-references. Add `commands/prd.md`, `commands/spec.md`, `commands/sync.md` as thin wrappers that invoke the corresponding skills.

**Tech Stack:** Claude Code plugin format (JSON manifest + Markdown skill/command files). No new code, no dependencies.

---

## Overview of changes

| Action | File |
|--------|------|
| Create | `.claude-plugin/plugin.json` |
| Create | `.claude-plugin/marketplace.json` |
| Git rename | `skills/roadmap-to-github-project/` → `skills/plan-sync/` |
| Modify | `skills/plan-sync/SKILL.md` — update `name:` frontmatter + internal refs |
| Modify | `skills/create-prd/SKILL.md` — update skill name refs |
| Modify | `skills/create-tech-spec/SKILL.md` — update skill name refs |
| Modify | `skills/INSTALL.md` — rename + update URLs |
| Modify | `skills/INSTALL.agent.md` — rename + update URLs |
| Modify | `README.md` — update skill table + add plugin install section |
| Modify | `examples/README.md` — update skill name ref |
| Modify | `examples/full-workflow/README.md` — update skill name ref |
| Create | `commands/prd.md` |
| Create | `commands/spec.md` |
| Create | `commands/sync.md` |

All work is done in `.worktrees/feat/claude-plugin` (branch `feat/claude-plugin`).

---

### Task 1: Plugin manifest

**Files:**
- Create: `.claude-plugin/plugin.json`

**Step 1: Create the directory and manifest**

```bash
mkdir -p .claude-plugin
```

Create `.claude-plugin/plugin.json`:

```json
{
  "name": "planpilot",
  "version": "1.0.0",
  "description": "Sync roadmap plans (epics/stories/tasks) to GitHub Issues and Projects v2",
  "author": {
    "name": "Arye Kogan",
    "url": "https://github.com/aryeko/planpilot"
  },
  "homepage": "https://github.com/aryeko/planpilot",
  "repository": "https://github.com/aryeko/planpilot",
  "license": "MIT",
  "keywords": ["planning", "github", "roadmap", "issues", "projects"],
  "skills": ["./skills/"]
}
```

**Step 2: Verify valid JSON**

```bash
python3 -m json.tool .claude-plugin/plugin.json
```

Expected: prints the formatted JSON without error.

**Step 3: Create `marketplace.json`**

Create `.claude-plugin/marketplace.json`:

```json
{
  "name": "planpilot",
  "owner": {
    "name": "Arye Kogan",
    "email": "arye@kogan.dev"
  },
  "metadata": {
    "description": "Sync roadmap plans (epics/stories/tasks) to GitHub Issues and Projects v2"
  },
  "plugins": [
    {
      "name": "planpilot",
      "source": "./",
      "description": "Claude Code skills and commands for planning workflows: create PRDs, tech specs, and sync plans to GitHub Issues + Projects v2",
      "author": { "name": "Arye Kogan" },
      "homepage": "https://github.com/aryeko/planpilot",
      "repository": "https://github.com/aryeko/planpilot",
      "license": "MIT",
      "keywords": ["planning", "github", "roadmap", "issues", "projects", "prd", "spec"],
      "category": "workflow",
      "tags": ["planning", "github-projects", "roadmap", "prd", "tech-spec", "skills", "commands"]
    }
  ]
}
```

**Step 4: Verify both files are valid JSON**

```bash
python3 -m json.tool .claude-plugin/plugin.json > /dev/null && \
python3 -m json.tool .claude-plugin/marketplace.json > /dev/null && echo "OK"
```

Expected: `OK`

**Step 5: Commit**

```bash
git add .claude-plugin/
git commit -m "feat(plugin): add plugin.json and marketplace.json"
```

---

### Task 2: Rename skill directory

**Files:**
- Rename: `skills/roadmap-to-github-project/` → `skills/plan-sync/`
- Modify: `skills/plan-sync/SKILL.md`

**Step 1: Git rename the directory**

```bash
git mv skills/roadmap-to-github-project skills/plan-sync
```

**Step 2: Update `name:` frontmatter in SKILL.md**

In `skills/plan-sync/SKILL.md`, change the frontmatter `name:` field:

```yaml
# Before
name: roadmap-to-github-project

# After
name: plan-sync
```

**Step 3: Update description trigger phrases in SKILL.md**

In `skills/plan-sync/SKILL.md`, update `description:` — replace references to
`roadmap-to-github-project` with `plan-sync`. Also update any self-referential
mentions within the skill body (e.g. "Use when a user asks to run
`roadmap-to-github-project`" → `plan-sync`).

**Step 4: Verify frontmatter parses**

```bash
head -5 skills/plan-sync/SKILL.md
```

Expected: shows `name: plan-sync` in frontmatter.

**Step 5: Commit**

```bash
git add skills/plan-sync/ skills/roadmap-to-github-project
git commit -m "feat(plugin): rename roadmap-to-github-project skill to plan-sync"
```

---

### Task 3: Update cross-references in sibling skills

**Files:**
- Modify: `skills/create-prd/SKILL.md`
- Modify: `skills/create-tech-spec/SKILL.md`

**Step 1: Update `skills/create-prd/SKILL.md`**

Two occurrences to change:

```
# Before (line ~28)
use `roadmap-to-github-project`

# After
use `plan-sync`
```

```
# Before (line ~180)
run `/roadmap-to-github-project`

# After
run `/planpilot:sync`
```

**Step 2: Update `skills/create-tech-spec/SKILL.md`**

Two occurrences to change:

```
# Before (line ~27)
use `roadmap-to-github-project` instead

# After
use `plan-sync` instead
```

```
# Before (line ~260)
Run `roadmap-to-github-project`

# After
Run `/planpilot:sync`
```

**Step 3: Commit**

```bash
git add skills/create-prd/SKILL.md skills/create-tech-spec/SKILL.md
git commit -m "docs(skills): update cross-references from roadmap-to-github-project to plan-sync"
```

---

### Task 4: Update INSTALL files

**Files:**
- Modify: `skills/INSTALL.md`
- Modify: `skills/INSTALL.agent.md`

**Step 1: Update `skills/INSTALL.md`**

Replace all occurrences of `roadmap-to-github-project` with `plan-sync` throughout
the file. This covers:
- The skill overview description
- `mkdir` commands
- `cp` commands
- `curl` fetch URLs (both Option A and Option B)
- Update instructions
- Uninstall instructions
- Verify commands (`ls -la`, `head -5`)
- Expected frontmatter name check

The curl URLs change from:
```
https://raw.githubusercontent.com/aryeko/planpilot/main/skills/roadmap-to-github-project/SKILL.md
```
to:
```
https://raw.githubusercontent.com/aryeko/planpilot/main/skills/plan-sync/SKILL.md
```

**Step 2: Update `skills/INSTALL.agent.md`**

Same replacement — all occurrences of `roadmap-to-github-project` → `plan-sync`,
including the curl URL and the destination path.

**Step 3: Commit**

```bash
git add skills/INSTALL.md skills/INSTALL.agent.md
git commit -m "docs(skills): update INSTALL files to reference plan-sync skill"
```

---

### Task 5: Update README and examples

**Files:**
- Modify: `README.md`
- Modify: `examples/README.md`
- Modify: `examples/full-workflow/README.md`

**Step 1: Update `README.md` skill table and loop**

Find the skills table (around line 128):
```markdown
# Before
| `roadmap-to-github-project` | Sync specs to GitHub Issues + Projects v2 |

# After
| `plan-sync` | Sync specs to GitHub Issues + Projects v2 |
```

Find the install loop (around line 145):
```bash
# Before
for skill in create-prd create-tech-spec roadmap-to-github-project; do

# After
for skill in create-prd create-tech-spec plan-sync; do
```

**Step 2: Add Claude Code plugin section to `README.md`**

Find the existing **Skills** installation section in the README. Immediately after it,
add a new section:

```markdown
### Claude Code Plugin

Install the planpilot plugin directly in Claude Code:

```bash
claude plugin marketplace add https://github.com/aryeko/planpilot
claude plugin install planpilot@planpilot
```

Then use:
- `/planpilot:prd` — create a PRD from a feature idea
- `/planpilot:spec` — create a tech spec from a PRD
- `/planpilot:sync` — generate `.plans` JSON and sync to GitHub
```

**Step 3: Update `examples/README.md`**

Replace `roadmap-to-github-project` with `plan-sync`.

**Step 4: Update `examples/full-workflow/README.md`**

Replace `roadmap-to-github-project` with `plan-sync`.

**Step 5: Commit**

```bash
git add README.md examples/README.md examples/full-workflow/README.md
git commit -m "docs: update skill name references and add Claude Code plugin install section"
```

---

### Task 6: Create commands

**Files:**
- Create: `commands/prd.md`
- Create: `commands/spec.md`
- Create: `commands/sync.md`

**Step 1: Create `commands/prd.md`**

```markdown
---
description: Create a Product Requirements Document from a feature idea
allowed-tools: [Read, Glob, Grep, Write]
---

Use the Skill tool to invoke the `planpilot:create-prd` skill, then follow its workflow exactly.
```

**Step 2: Create `commands/spec.md`**

```markdown
---
description: Create a Technical Specification from a PRD
allowed-tools: [Read, Glob, Grep, Write, Bash]
---

Use the Skill tool to invoke the `planpilot:create-tech-spec` skill, then follow its workflow exactly.
```

**Step 3: Create `commands/sync.md`**

```markdown
---
description: Convert PRD/spec/roadmap to .plans JSON and sync to GitHub Issues + Projects v2
allowed-tools: [Read, Glob, Grep, Write, Bash]
---

Use the Skill tool to invoke the `planpilot:plan-sync` skill, then follow its workflow exactly.
```

**Step 4: Commit**

```bash
git add commands/
git commit -m "feat(plugin): add planpilot:prd, planpilot:spec, planpilot:sync commands"
```

---

### Task 7: Final validation

**Step 1: Run docs-links check**

```bash
poetry run poe docs-links
```

Expected: exits 0 with no broken link errors. If failures appear, fix the broken
references before continuing.

**Step 2: Run full check suite**

```bash
poetry run poe check
```

Expected: lint, format-check, typecheck, and tests all pass (509 tests).

**Step 3: Verify plugin structure**

```bash
find .claude-plugin commands skills/plan-sync -type f | sort
```

Expected output:
```
.claude-plugin/plugin.json
commands/prd.md
commands/spec.md
commands/sync.md
skills/plan-sync/SKILL.md
```

**Step 4: Verify plugin.json is valid JSON**

```bash
python3 -m json.tool .claude-plugin/plugin.json > /dev/null && echo "OK"
```

Expected: `OK`

**Step 5: Verify skill frontmatter**

```bash
head -5 skills/plan-sync/SKILL.md
```

Expected: frontmatter shows `name: plan-sync`.

**Step 6: Final commit if needed**

If any fixes were made in steps 1-2, commit them:

```bash
git add -p
git commit -m "fix(plugin): address docs-links and check issues"
```
