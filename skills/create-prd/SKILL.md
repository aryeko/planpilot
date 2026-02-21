---
name: create-prd
description: Use when a user has a feature idea and wants to create a structured Product Requirements Document (PRD). Guides through discovery questions and produces a Markdown PRD with YAML frontmatter.
---

# Create PRD

## Overview

Guided skill that takes a brief feature idea and produces a structured Product Requirements Document through interactive discovery questions. The agent asks targeted questions to understand motivation, scope, audience, and success criteria, then generates a comprehensive PRD with YAML frontmatter and all nine required sections.

## Skill Invocation Gate (MANDATORY)

Before any action, list available skills and invoke all that apply. If installed and applicable, you MUST use them. Process skills take priority over implementation skills.

## Prerequisites

None. This skill requires only an agent with no external tools or dependencies.

## When to Use

- User wants to write or create a PRD
- User has a feature idea and wants to formalize it
- User wants to define product requirements before starting technical work
- User says "let's plan a feature", "create a PRD", or similar
- User is beginning a new project or feature initiative

Do **not** use when the user already has a completed PRD and wants a technical specification (use `create-tech-spec`), the user wants to generate `.plans` JSON artifacts (use `plan-sync`), or the user is asking to implement feature requirements.

## Inputs

- Brief idea description from user (text prompt, typically 2–5 sentences)

## Outputs

- `docs/prd/<slug>-prd.md` — Markdown file with YAML frontmatter containing a complete PRD

---

## Frontmatter Schema

Every PRD must include YAML frontmatter with these fields:

```yaml
---
title: "Feature Title"
status: draft | review | approved
created: YYYY-MM-DD
author: <user or auto-detected>  # optional
tags: [tag1, tag2]
---
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | yes | Feature or capability name |
| `status` | enum | yes | `draft`, `review`, or `approved` |
| `created` | string | yes | ISO 8601 date (YYYY-MM-DD) |
| `author` | string | no | User name or email; can be auto-detected from git config |
| `tags` | array | no | Feature categorization tags for discoverability |

---

## PRD Template — Nine Sections

Every PRD must include these nine sections. Use this guidance when generating each section:

### 1. Overview
One-paragraph summary of what is being built and why it matters. Answer: "What is this feature?" and "Why is it important?"

**Guidance:** Short, executive summary. Should be understandable to someone unfamiliar with the product. Avoid implementation details.

### 2. Motivation
Explain why this feature matters **now**. Include business case, market opportunity, or user pain point being solved.

**Guidance:** Connect to larger product strategy or customer needs. Clarify urgency if there's a deadline or competitive pressure.

### 3. Goals & Non-Goals
Explicit in-scope and out-of-scope boundaries. What are we committing to? What are we explicitly **not** doing?

**Guidance:** Use two subsections: "Goals" (what we're building) and "Non-Goals" (what we're deferring). Be explicit — vagueness leads to scope creep. Non-goals are critical.

### 4. Target Audience
Who benefits from this feature? Describe their context, needs, and how they'll interact with it.

**Guidance:** Include user personas, customer segments, or internal stakeholders. Be specific about user context.

### 5. Requirements
Functional requirements — what the feature must do. **All requirements must be numbered and verifiable.**

**Guidance:** Each requirement should be testable. Avoid vague language like "make it fast" — instead write "page load completes within 2 seconds". Requirements are not implementation steps; they describe the "what", not the "how".

### 6. Success Metrics
Measurable outcomes that prove the feature works and delivers value. What data do we track?

**Guidance:** Include adoption metrics, performance targets, quality gates, and business KPIs. Each metric must have a target value or threshold. Examples: "80% task completion rate", "API response time < 200ms".

### 7. Diagrams
Visual aids that clarify the feature. Include mermaid flowcharts, system context diagrams, data flow diagrams, or user journey maps where they improve understanding.

**Guidance:** At least one diagram is expected. Diagrams should answer questions like "what system components are involved?", "what's the flow of data?", or "how does the user interact with the system?". Use mermaid syntax.

### 8. Constraints & Assumptions
Business or technical constraints that bound the solution. Assumptions made during discovery.

**Guidance:** Examples of constraints: "must integrate with existing payment system", "mobile-only in Phase 1", "GDPR-compliant". Examples of assumptions: "users have stable internet", "admin panel available for configuration".

### 9. Open Questions
Unresolved items flagged for follow-up before implementation starts. What do we need to learn or decide?

**Guidance:** Frame as questions, not complaints. Examples: "How will we handle offline sync?", "Which payment providers do we support in v1?". This section prevents surprises during development.

---

## File Naming Convention

| Component | Format | Example |
|-----------|--------|---------|
| Directory | `docs/prd/` | — |
| Filename | `<slug>-prd.md` | `user-authentication-prd.md` |
| Slug | lowercase, hyphenated, derived from title | Title: "User Authentication" → slug: `user-authentication` |

**Important:** Slugs are derived from the PRD title, NOT from a date prefix. The created date goes in frontmatter only.

---

## Workflow — Step by Step for the Agent

### Step 1: Initial Context

User provides a brief feature idea (typically 1–5 sentences). Acknowledge the idea and explain that you'll ask a series of discovery questions to understand the scope, motivation, and requirements.

### Step 2: Discovery Questions

Ask questions **one at a time** to build understanding. Continue until you have enough context (~5–8 questions, depending on feature complexity). Example sequence:

1. **Motivation:** "Why is this feature important? What problem does it solve or what opportunity does it unlock?"
2. **Target Audience:** "Who will use this feature? Are they customers, internal teams, or both?"
3. **Scope Boundary:** "What's the smallest version of this feature that would be valuable? What are we deferring to later?"
4. **Key Requirements:** "What must the feature do to be useful? What are the non-negotiable capabilities?"
5. **Success Definition:** "How will we know this feature is successful? What metrics matter?"
6. **Constraints:** "Are there any technical, business, or regulatory constraints we should keep in mind?"
7. **Dependencies:** "Does this feature depend on other systems or capabilities? Any blockers?"

Adjust based on user responses. If the user provides rich context early, skip to the next unanswered question.

### Step 3: Synthesis and Draft

Once you have sufficient context, synthesize the discovery into a PRD draft:
1. Generate YAML frontmatter with title (from user's original idea or refined during discussion), status `draft`, today's date, author (auto-detected or blank), and relevant tags
2. Write all nine sections based on discovery answers
3. Include at least one mermaid diagram (flowchart, system diagram, or user journey)
4. Ensure all requirements are numbered and verifiable
5. Define explicit success metrics with measurable targets
6. Populate "Open Questions" with any gaps discovered during writing

### Step 4: Review and Iteration

Present the draft PRD to the user:
- Display the full PRD with formatted sections
- Ask: "Does this capture the feature correctly? What should we change?"
- Collect feedback and iterate on specific sections
- Update requirements, metrics, or scope as needed
- Repeat until user approves

### Step 5: File Creation

Once approved:
1. Derive slug from PRD title (lowercase, hyphenated)
2. Create `docs/prd/` directory if it doesn't exist
3. Write the approved PRD to `docs/prd/<slug>-prd.md`
4. Confirm file path and content saved

### Step 6: Next Steps

Suggest next action:

> PRD saved to `docs/prd/<slug>-prd.md`. Ready for the next step?
>
> Run `/planpilot:spec` to generate a technical specification from this PRD, which will detail how to build it. After approving the spec, run `/planpilot:sync` to decompose it into epics, stories, and tasks synced to GitHub.

---

## Common Mistakes

- **Jumping to writing without discovery questions** — skipping questions leads to incomplete or misdirected PRDs. Always ask 5–8 targeted questions first.
- **Vague, unverifiable requirements** — "make it fast" is not a requirement; "page load completes within 2 seconds" is. Every requirement must be testable.
- **Including implementation details** — a PRD is about "what" and "why", not "how". Technical decisions go in the tech spec. If a user pushes technical details, gently redirect: "That's great detail — let's capture that in the tech spec. For now, what *must* the feature do?"
- **Forgetting non-goals** — explicitly stating what's out of scope is as important as stating what's in scope. Prevents scope creep.
- **Skipping success metrics or making them unmeasurable** — "users like it" is not a metric; "80% of feature users return weekly" is. Metrics must have targets.
- **Forgetting diagrams** — at least one diagram is expected in every PRD. If the user doesn't describe visual complexity, ask: "Should we add a diagram showing the user flow or system components?"
- **Not asking about constraints** — technical or business constraints heavily influence design. Always ask about integrations, compliance, platform constraints, etc.
- **Leaving open questions incomplete** — if gaps exist, flag them as open questions rather than pretending certainty. This prevents rework during implementation.
- **Saving PRD without approval** — always present a draft and iterate with user feedback before saving the file.

## Completion Criteria

This skill run is complete when:

1. PRD file saved to `docs/prd/<slug>-prd.md`
2. YAML frontmatter includes `title`, `status` (draft), `created` (today's date), and `tags`; `author` is optional
3. All nine sections are present and substantive (not placeholder text)
4. Every requirement is numbered and verifiable (not vague)
5. Success metrics are measurable with explicit targets
6. At least one mermaid diagram is included
7. Non-goals section is explicit and clear
8. Open questions section flags any unresolved items
9. User has reviewed and approved the draft before file save
