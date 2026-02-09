# Install: `roadmap-to-github-project` Skill

This installs the planpilot skill into the open discovery path used by agent platforms that support filesystem skills:

- `~/.agents/skills/<skill-name>/SKILL.md`

## Agent Self-Install

Tell your agent:

> Fetch and follow instructions from https://raw.githubusercontent.com/aryeko/planpilot/refs/heads/main/skills/INSTALL.agent.md

The agent will install both `planpilot` and the skill automatically.

## Manual Install

### 1) Prerequisites

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

### 2) Install `pipx` (if not already installed)

[`pipx`](https://pipx.pypa.io/) installs CLI tools in isolated environments -- avoids PEP 668 / "externally managed environment" errors on macOS Homebrew and system Python.

```bash
pipx --version
```

If `pipx` is not found:

```bash
# macOS
brew install pipx
pipx ensurepath

# Debian / Ubuntu
sudo apt install -y pipx
pipx ensurepath
```

You may need to restart your shell after `ensurepath`.

### 3) Install `planpilot`

```bash
pipx install planpilot
```

Verify:

```bash
planpilot --version
```

### 4) Install the skill into open skill path

Create destination directory:

```bash
mkdir -p ~/.agents/skills/roadmap-to-github-project
```

#### Option A: Copy from local repo checkout

```bash
cp skills/roadmap-to-github-project/SKILL.md \
  ~/.agents/skills/roadmap-to-github-project/SKILL.md
```

#### Option B: Fetch from GitHub raw URL

```bash
curl -fsSL "https://raw.githubusercontent.com/aryeko/planpilot/main/skills/roadmap-to-github-project/SKILL.md" \
  -o ~/.agents/skills/roadmap-to-github-project/SKILL.md
```

If your skill is on a branch, replace `main` with that branch name.

### 5) Verify skill install

```bash
ls -la ~/.agents/skills/roadmap-to-github-project
head -5 ~/.agents/skills/roadmap-to-github-project/SKILL.md
```

Expected frontmatter should include:

- `name: roadmap-to-github-project`

### 6) Restart your agent

**Restart your agent** (start a new session) so it discovers the newly installed skill. The skill won't be available until the agent re-scans `~/.agents/skills/`.

### 7) Update / uninstall

Update (re-copy or re-fetch `SKILL.md`):

```bash
curl -fsSL "https://raw.githubusercontent.com/aryeko/planpilot/main/skills/roadmap-to-github-project/SKILL.md" \
  -o ~/.agents/skills/roadmap-to-github-project/SKILL.md
```

Uninstall:

```bash
rm -rf ~/.agents/skills/roadmap-to-github-project
```
