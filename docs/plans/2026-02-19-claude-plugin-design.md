# Design: planpilot Claude Code Plugin

**Date:** 2026-02-19
**Branch:** `feat/claude-plugin`
**Status:** Approved

## Overview

Package planpilot's existing skills and add slash commands as a Claude Code plugin distributed via a self-hosted GitHub marketplace. The plugin lives in the planpilot repo itself (Approach A) — same pattern used by ecc-conveyor.

## File Structure

```
planpilot/
├── .claude-plugin/
│   └── plugin.json              ← new: plugin manifest
├── skills/
│   ├── create-prd/SKILL.md      ← existing (unchanged)
│   ├── create-tech-spec/SKILL.md ← existing (unchanged)
│   └── plan-sync/SKILL.md       ← renamed from roadmap-to-github-project/
└── commands/
    ├── prd.md                   ← new: /planpilot:prd
    ├── spec.md                  ← new: /planpilot:spec
    └── sync.md                  ← new: /planpilot:sync
```

No hooks. No agents. Skills and commands only.

## Plugin Manifest (`.claude-plugin/plugin.json`)

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

## Skills

| Directory | Skill `name` | Change |
|---|---|---|
| `skills/create-prd/` | `create-prd` | No change |
| `skills/create-tech-spec/` | `create-tech-spec` | No change |
| `skills/plan-sync/` | `plan-sync` | Renamed from `roadmap-to-github-project` |

The skill rename requires:
1. Rename directory: `skills/roadmap-to-github-project/` → `skills/plan-sync/`
2. Update `name:` frontmatter in `SKILL.md`: `roadmap-to-github-project` → `plan-sync`
3. Update `description:` trigger phrases to reference new name
4. Update `skills/INSTALL.md` and `skills/INSTALL.agent.md` to reflect the rename

## Commands

Three slash commands namespaced as `planpilot:`, each invoking the corresponding skill.

### `/planpilot:prd`
- Invokes the `create-prd` skill
- Guides user through PRD creation via interactive discovery questions
- `allowed-tools: [Read, Glob, Grep, Write]`

### `/planpilot:spec`
- Invokes the `create-tech-spec` skill
- Takes a PRD and generates a codebase-aware technical specification
- `allowed-tools: [Read, Glob, Grep, Write, Bash]`

### `/planpilot:sync`
- Invokes the `plan-sync` skill
- Converts PRD/spec/roadmap → `.plans` JSON → GitHub Issues + Projects v2
- Supports three modes: plan-only, sync-only, full
- `allowed-tools: [Read, Glob, Grep, Write, Bash]`

## Distribution

The planpilot repo acts as its own single-plugin marketplace (no separate repo needed).

**User install:**
```bash
claude plugin marketplace add https://github.com/aryeko/planpilot
claude plugin install planpilot@planpilot
```

**Updating:** Skills and commands update automatically when the user updates the plugin, which tracks the planpilot release cycle.

## Impact on Existing `skills/INSTALL.md` Flow

The existing `~/.agents/skills/` install path (used by non-Claude-Code agent platforms) remains valid and unchanged. The Claude Code plugin is an additional distribution channel, not a replacement. Both install paths coexist.

## Out of Scope

- MCP server
- Hooks
- Agents
- `init` / `validate` commands
- Submission to `anthropics/claude-plugins-official`
