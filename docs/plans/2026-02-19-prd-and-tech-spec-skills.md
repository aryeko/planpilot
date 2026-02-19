# PRD and Tech Spec Skills Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create two new SKILL.md files (`create-prd` and `create-tech-spec`) and update installation docs to include them.

**Architecture:** Two independent skills following the same pattern as `roadmap-to-github-project`. Each skill is a standalone SKILL.md with frontmatter, workflow, and section definitions. Installation docs updated to cover all three skills.

**Tech Stack:** Markdown SKILL.md files, YAML frontmatter, mermaid diagrams

**Design doc:** `docs/plans/2026-02-19-prd-and-tech-spec-skills-design.md`

---

### Task 1: Create `create-prd` SKILL.md

**Files:**
- Create: `skills/create-prd/SKILL.md`

**Step 1: Create the skill directory**

```bash
mkdir -p skills/create-prd
```

**Step 2: Write `skills/create-prd/SKILL.md`**

Write the full SKILL.md following the same structure as `skills/roadmap-to-github-project/SKILL.md`. Include:

Frontmatter:
```yaml
---
name: create-prd
description: Use when a user has a feature idea and wants to create a structured Product Requirements Document (PRD). Guides through discovery questions and produces a Markdown PRD with YAML frontmatter.
---
```

Sections to include in the skill file (in order):
1. **Overview** — one-paragraph summary of what the skill does
2. **Skill Invocation Gate** — same mandatory gate as the roadmap skill
3. **Prerequisites** — none (no tools required, just an agent)
4. **When to Use** — triggers: user wants to write a PRD, has an idea to formalize, wants to define product requirements
5. **Inputs** — brief idea description from user (text)
6. **Outputs** — `docs/prd/<slug>-prd.md` with frontmatter schema definition
7. **PRD Template** — define the 9 sections with descriptions and guidance for each:
   1. Overview — what we're building, one paragraph
   2. Motivation — why this matters now
   3. Goals & Non-Goals — explicit in/out scope
   4. Target Audience — who benefits
   5. Requirements — functional requirements, numbered, verifiable
   6. Success Metrics — measurable outcomes
   7. Diagrams — mermaid flow/context diagrams
   8. Constraints & Assumptions — business/technical constraints
   9. Open Questions — unresolved items
8. **Frontmatter Schema** — document the YAML frontmatter fields: title, status (draft/review/approved), created, author, tags
9. **File Naming** — `docs/prd/<slug>-prd.md`, slug rules (lowercase, hyphenated from title)
10. **Workflow** — step-by-step:
    1. User provides brief idea
    2. Ask structured questions one at a time (motivation, audience, scope, requirements, success criteria)
    3. Generate PRD draft
    4. Present for review, iterate on feedback
    5. Save to `docs/prd/`
    6. Suggest next step: "Run `create-tech-spec` to generate a technical specification from this PRD"
11. **Common Mistakes** — pitfalls to avoid (skipping questions, vague requirements, mixing implementation details into PRD, forgetting diagrams)
12. **Completion Criteria** — when the skill run is done

Reference the existing `skills/roadmap-to-github-project/SKILL.md` for formatting conventions, tone, and structure.

**Step 3: Verify valid markdown**

```bash
python3 -m json.tool /dev/null 2>/dev/null; head -5 skills/create-prd/SKILL.md
```

Verify frontmatter starts with `---` and includes `name: create-prd`.

**Step 4: Commit**

```bash
git add skills/create-prd/SKILL.md
git commit -m "feat(skills): add create-prd skill"
```

---

### Task 2: Create `create-tech-spec` SKILL.md

**Files:**
- Create: `skills/create-tech-spec/SKILL.md`

**Step 1: Create the skill directory**

```bash
mkdir -p skills/create-tech-spec
```

**Step 2: Write `skills/create-tech-spec/SKILL.md`**

Frontmatter:
```yaml
---
name: create-tech-spec
description: Use when a user has a PRD and wants to create a codebase-aware technical specification. Analyzes the existing codebase and PRD to produce an architecture-level spec with mermaid diagrams.
---
```

Sections to include (in order):
1. **Overview** — one-paragraph summary
2. **Skill Invocation Gate** — mandatory gate
3. **Prerequisites** — access to the codebase (agent must be in a project directory)
4. **When to Use** — triggers: user has a PRD and wants a tech spec, wants to design the technical approach for a feature
5. **Inputs** — PRD file path + codebase access
6. **Outputs** — `docs/specs/<slug>-spec.md` with frontmatter schema
7. **Frontmatter Schema** — title, status, created, prd (path to source PRD), author, tags
8. **Spec Template — Fixed Sections** — always-present sections:
   1. Overview — summary from PRD
   2. System Context — how it fits in existing architecture + mermaid context diagram
   3. Technical Requirements — PRD requirements translated to technical constraints
9. **Spec Template — Dynamic Design Sections** — skill selects relevant sections from palette:
   - Components & Architecture (+ mermaid component/flowchart)
   - Data Model (+ mermaid ER)
   - API Design
   - Integration Points
   - State Management
   - Security Model
   - Performance Considerations

   Document the selection criteria: skill analyzes PRD requirements and codebase to determine which sections apply. Include guidance on when each section is relevant.
10. **Spec Template — Fixed Closing Sections**:
    1. Technical Decisions — key choices with rationale
    2. Validation — test strategy, acceptance criteria, verification commands
    3. Risks & Mitigations — technical risks
    4. Open Questions — unresolved items
11. **Codebase Analysis Steps** — what the skill examines:
    - Project structure (directories, entry points)
    - Existing modules that will be touched
    - Architectural patterns in use
    - Similar existing features for consistency
    - Map PRD requirements to technical components
12. **Diagram Policy** — all diagrams use mermaid; include them in System Context and wherever they improve understanding
13. **File Naming** — `docs/specs/<slug>-spec.md`, slug rules
14. **Workflow** — step-by-step:
    1. Read PRD file, parse frontmatter + sections
    2. Analyze codebase
    3. Map PRD requirements to components
    4. Determine relevant dynamic sections
    5. Generate spec draft with mermaid diagrams
    6. Present for review, iterate
    7. Save to `docs/specs/`
    8. Suggest: "Run `roadmap-to-github-project` to decompose this spec into epics, stories, and tasks"
15. **Common Mistakes** — pitfalls (skipping codebase analysis, missing diagrams, over-specifying implementation details for architecture-level spec, not linking back to PRD)
16. **Completion Criteria**

**Step 3: Verify frontmatter**

```bash
head -5 skills/create-tech-spec/SKILL.md
```

Verify `name: create-tech-spec` in frontmatter.

**Step 4: Commit**

```bash
git add skills/create-tech-spec/SKILL.md
git commit -m "feat(skills): add create-tech-spec skill"
```

---

### Task 3: Update INSTALL.md to include all three skills

**Files:**
- Modify: `skills/INSTALL.md`

**Step 1: Read current file**

Read `skills/INSTALL.md` to understand current structure.

**Step 2: Update to cover all three skills**

Update section headers and install commands to include `create-prd` and `create-tech-spec` alongside `roadmap-to-github-project`. The manual install steps (mkdir + curl/cp) should list all three skills. Keep the same structure but expand to three skills.

Example additions to the manual install section:

```bash
mkdir -p ~/.agents/skills/create-prd
mkdir -p ~/.agents/skills/create-tech-spec

curl -fsSL "https://raw.githubusercontent.com/aryeko/planpilot/main/skills/create-prd/SKILL.md" \
  -o ~/.agents/skills/create-prd/SKILL.md

curl -fsSL "https://raw.githubusercontent.com/aryeko/planpilot/main/skills/create-tech-spec/SKILL.md" \
  -o ~/.agents/skills/create-tech-spec/SKILL.md
```

Update the verification section to check all three skills.

**Step 3: Commit**

```bash
git add skills/INSTALL.md
git commit -m "docs(skills): update install guide for all three skills"
```

---

### Task 4: Update INSTALL.agent.md for all three skills

**Files:**
- Modify: `skills/INSTALL.agent.md`

**Step 1: Read current file**

Read `skills/INSTALL.agent.md`.

**Step 2: Update Step 5 (Install the skill) to install all three skills**

Add mkdir + curl commands for `create-prd` and `create-tech-spec`. Update Step 6 verification to check all three. Update Step 7 report to list all three installed skills.

**Step 3: Commit**

```bash
git add skills/INSTALL.agent.md
git commit -m "docs(skills): update agent install for all three skills"
```

---

### Task 5: Update README.md skill install section

**Files:**
- Modify: `README.md:120-150` (Install Agent Skill section)

**Step 1: Read the current Install Agent Skill section**

Read `README.md` lines 120-150.

**Step 2: Update to mention all three skills**

Update the "Manual Install" subsection to show installation of all three skills (or reference INSTALL.md for the full list). Keep it concise — the README should show the quickest path, not exhaustive instructions.

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README skill install for all three skills"
```

---

### Task 6: Verify all links and commit final

**Step 1: Run docs-links check**

```bash
poetry run poe docs-links
```

Expected: all links pass (no broken references).

**Step 2: Verify skill files exist and have correct frontmatter**

```bash
head -3 skills/create-prd/SKILL.md
head -3 skills/create-tech-spec/SKILL.md
head -3 skills/roadmap-to-github-project/SKILL.md
```

All three should show `name:` in frontmatter.

**Step 3: Fix any broken links if found**

If docs-links reports issues, fix them and commit.
