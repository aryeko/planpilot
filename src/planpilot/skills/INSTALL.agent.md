# Agent Install: planpilot Skills

You are installing the **planpilot** skills: `create-prd`, `create-tech-spec`, and `plan-sync`.

Follow every step below **in order**. Do not skip steps. Report results to the user after each major step.

## Step 1: Check Python

Run:

```bash
python3 --version
```

If `python3` is not found, try `python --version`. You need Python 3.11+.

If Python is not installed, STOP and tell the user:

> Python 3.11+ is required. Please install it from https://python.org and try again.

## Step 2: Install planpilot

First, try `uvx` (zero-install, preferred — no separate install step):

```bash
uvx planpilot --version
```

If that succeeds, **skip to Step 3** — `uvx planpilot` is your invocation for all subsequent commands.

If `uvx` is not found, install `uv`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then retry `uvx planpilot --version`. If it works, skip to Step 3.

**Fallback — install via `pipx`:**

Check if `pipx` is installed:

```bash
pipx --version
```

If `pipx` is **not found**, install it:

- **macOS (Homebrew)**:
  ```bash
  brew install pipx
  pipx ensurepath
  ```
- **Debian / Ubuntu**:
  ```bash
  sudo apt install -y pipx
  pipx ensurepath
  ```
- **Other / fallback**:
  ```bash
  python3 -m pip install --user pipx
  python3 -m pipx ensurepath
  ```

After installing pipx, you may need to open a new shell or `source ~/.bashrc` / `source ~/.zshrc` for PATH to update.

```bash
pipx install planpilot
```

If this fails, STOP and tell the user the error output.

## Step 3: Verify planpilot

Run (try in order until one succeeds):

```bash
uvx planpilot --version
```

```bash
planpilot --version
```

```bash
python3 -m planpilot --version
```

```bash
python -m planpilot --version
```

If none work, STOP and report the failure to the user.

**Remember which invocation worked** and use it for all subsequent commands.

## Step 4: Install the skills

Install `plan-sync`:

```bash
mkdir -p ~/.agents/skills/plan-sync
```

```bash
curl -fsSL "https://raw.githubusercontent.com/aryeko/planpilot/main/src/planpilot/skills/plan-sync/SKILL.md" \
  -o ~/.agents/skills/plan-sync/SKILL.md
```

Install `create-prd`:

```bash
mkdir -p ~/.agents/skills/create-prd
```

```bash
curl -fsSL "https://raw.githubusercontent.com/aryeko/planpilot/main/src/planpilot/skills/create-prd/SKILL.md" \
  -o ~/.agents/skills/create-prd/SKILL.md
```

Install `create-tech-spec`:

```bash
mkdir -p ~/.agents/skills/create-tech-spec
```

```bash
curl -fsSL "https://raw.githubusercontent.com/aryeko/planpilot/main/src/planpilot/skills/create-tech-spec/SKILL.md" \
  -o ~/.agents/skills/create-tech-spec/SKILL.md
```

If `curl` is not available, try `wget` for any of the above (replace `curl -fsSL ... -o` with `wget -qO`).

## Step 5: Verify skill install

Verify all three skills were installed:

```bash
head -5 ~/.agents/skills/plan-sync/SKILL.md
```

Should contain `name: plan-sync`.

```bash
head -5 ~/.agents/skills/create-prd/SKILL.md
```

Should contain `name: create-prd`.

```bash
head -5 ~/.agents/skills/create-tech-spec/SKILL.md
```

Should contain `name: create-tech-spec`.

If any are missing or incorrect, retry Step 4.

## Step 6: Report to user

Tell the user:

> **planpilot skills installed successfully.**
>
> - `planpilot` CLI: installed and verified
> - Skills installed:
>   - `~/.agents/skills/plan-sync/SKILL.md`
>   - `~/.agents/skills/create-prd/SKILL.md`
>   - `~/.agents/skills/create-tech-spec/SKILL.md`
>
> **Please restart your agent** (start a new session) so it discovers the newly installed skills. The skills won't be available until the agent re-scans `~/.agents/skills/`.
>
> After restarting, you can:
> - Ask me to turn a roadmap or spec into a GitHub project
> - Ask me to create a Product Requirements Document (PRD)
> - Ask me to create a Technical Specification (Tech Spec)
>
> To update the skills later, re-run this install or update individual skills with curl.
