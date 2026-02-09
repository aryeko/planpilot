# Install: `spec-to-planpilot-sync` Skill (Single Skill, Open Standard)

This installs one skill into the open discovery path used by agent platforms that support filesystem skills:

- `~/.agents/skills/<skill-name>/SKILL.md`

## 1) Prerequisites

Check Python 3 is available:

```bash
python3 --version
```

Optional strict check (requires Python 3.11+):

```bash
python3 - <<'PY'
import sys
assert sys.version_info >= (3, 11), f"Need Python 3.11+, got {sys.version}"
print("OK:", sys.version)
PY
```

Check pip is available:

```bash
python3 -m pip --version
```

## 2) Install `planpilot`

Important: `python3 -m pip install -g planpilot` is **not valid** (`pip` has no `-g` flag).

Use one of these:

```bash
# Recommended user install (no sudo)
python3 -m pip install --user --upgrade planpilot
```

```bash
# Alternative (inside a virtualenv)
python3 -m pip install --upgrade planpilot
```

Verify installation:

```bash
planpilot --version || python3 -m planpilot --version
```

## 3) Install this single skill into open skill path

Create destination directory:

```bash
mkdir -p ~/.agents/skills/spec-to-planpilot-sync
```

### Option A: Copy from local repo checkout

```bash
cp /ABSOLUTE/PATH/TO/planpilot/skills/roadmap-to-github-project/SKILL.md \
  ~/.agents/skills/spec-to-planpilot-sync/SKILL.md
```

### Option B: Fetch from GitHub raw URL

```bash
curl -fsSL "https://raw.githubusercontent.com/aryeko/planpilot/main/skills/roadmap-to-github-project/SKILL.md" \
  -o ~/.agents/skills/spec-to-planpilot-sync/SKILL.md
```

If your skill is on a branch, replace `main` with that branch name.

## 4) Verify skill install

```bash
ls -la ~/.agents/skills/spec-to-planpilot-sync
sed -n '1,40p' ~/.agents/skills/spec-to-planpilot-sync/SKILL.md
```

Expected frontmatter should include:

- `name: spec-to-planpilot-sync`

## 5) Restart your agent tool

Restart the agent CLI/app so it re-discovers skills from `~/.agents/skills/`.

## 6) Update / uninstall

Update (re-copy or re-fetch `SKILL.md`):

```bash
# example via curl
curl -fsSL "https://raw.githubusercontent.com/aryeko/planpilot/main/skills/roadmap-to-github-project/SKILL.md" \
  -o ~/.agents/skills/spec-to-planpilot-sync/SKILL.md
```

Uninstall:

```bash
rm -rf ~/.agents/skills/spec-to-planpilot-sync
```
