# Plugin Reference

Quick lookup for the planpilot Claude Code plugin: commands, skill locations, and install methods.

## Plugin commands

| Command | Skill | Description |
|---------|-------|-------------|
| `/planpilot:prd` | `create-prd` | Generate a structured PRD from a feature idea |
| `/planpilot:spec` | `create-tech-spec` | Generate a codebase-aware tech spec from a PRD |
| `/planpilot:sync` | `plan-sync` | Generate `.plans` JSON and sync to GitHub Issues + Projects v2 |

## Install methods

### Claude Code Plugin (pip, recommended)

```bash
claude plugin marketplace add aryeko/planpilot
claude plugin install planpilot@planpilot
```

The planpilot CLI is installed automatically from PyPI. No separate `pip install` needed.

### Agent self-install

```
Fetch and follow instructions from https://raw.githubusercontent.com/aryeko/planpilot/main/src/planpilot/skills/INSTALL.agent.md
```

### Manual (filesystem skills)

```bash
for skill in create-prd create-tech-spec plan-sync; do
  mkdir -p ~/.agents/skills/$skill
  curl -fsSL "https://raw.githubusercontent.com/aryeko/planpilot/main/src/planpilot/skills/$skill/SKILL.md" \
    -o ~/.agents/skills/$skill/SKILL.md
done
```

## Skill files

| File | Purpose |
|------|---------|
| `src/planpilot/skills/create-prd/SKILL.md` | PRD generation skill definition |
| `src/planpilot/skills/create-tech-spec/SKILL.md` | Tech spec generation skill definition |
| `src/planpilot/skills/plan-sync/SKILL.md` | Plan sync skill definition |
| `src/planpilot/skills/INSTALL.md` | Manual install instructions |
| `src/planpilot/skills/INSTALL.agent.md` | Agent self-install instructions |

## Plugin manifest files

| File | Purpose |
|------|---------|
| `src/planpilot/.claude-plugin/plugin.json` | Plugin manifest: name, version, author, skills, commands |
| `src/planpilot/.claude-plugin/marketplace.json` | Marketplace registry entry: owner, pip source |

## Related

- [Plugin and Skills Guide](../guides/plugin-skills-guide.md) — walkthrough and troubleshooting
- [CLI Reference](./cli-reference.md) — `planpilot sync` / `clean` / `map sync` flags
