# Agent Install: `roadmap-to-github-project` Skill

You are installing the **planpilot** skill for roadmap-to-GitHub-project sync.

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

Try each in order until one succeeds:

```bash
pip install --upgrade planpilot
```

```bash
pip3 install --upgrade planpilot
```

```bash
python3 -m pip install --upgrade planpilot
```

```bash
python -m pip install --upgrade planpilot
```

If all fail, STOP and tell the user the error output. Common issues:
- No pip: suggest `python3 -m ensurepip --upgrade`
- Permission denied: suggest adding `--user` flag

## Step 3: Verify planpilot

Run (try in order until one succeeds):

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

## Step 4: Install the skill

```bash
mkdir -p ~/.agents/skills/roadmap-to-github-project
```

```bash
curl -fsSL "https://raw.githubusercontent.com/aryeko/planpilot/main/skills/roadmap-to-github-project/SKILL.md" \
  -o ~/.agents/skills/roadmap-to-github-project/SKILL.md
```

If `curl` is not available, try `wget`:

```bash
wget -qO ~/.agents/skills/roadmap-to-github-project/SKILL.md \
  "https://raw.githubusercontent.com/aryeko/planpilot/main/skills/roadmap-to-github-project/SKILL.md"
```

## Step 5: Verify skill install

```bash
head -5 ~/.agents/skills/roadmap-to-github-project/SKILL.md
```

The output must contain `name: roadmap-to-github-project`. If not, the download failed — retry Step 4.

## Step 6: Report to user

Tell the user:

> **planpilot skill installed successfully.**
>
> - `planpilot` CLI: installed and verified
> - Skill: `~/.agents/skills/roadmap-to-github-project/SKILL.md`
>
> **Please restart your agent** (start a new session) so it discovers the newly installed skill. The skill won't be available until the agent re-scans `~/.agents/skills/`.
>
> After restarting, ask me to turn a roadmap or spec into a GitHub project.
>
> To update the skill later, re-run this install or run:
> ```
> curl -fsSL "https://raw.githubusercontent.com/aryeko/planpilot/main/skills/roadmap-to-github-project/SKILL.md" \
>   -o ~/.agents/skills/roadmap-to-github-project/SKILL.md
> ```
