def bullets(items: list[str]) -> str:
    if not items:
        return "* (none)"
    return "\n".join([f"* {i}" for i in items])


def scope_block(scope: dict[str, object]) -> str:
    scope_in = scope.get("in", []) if isinstance(scope, dict) else []
    scope_out = scope.get("out", []) if isinstance(scope, dict) else []
    return f"In:\n\n{bullets(scope_in)}\n\nOut:\n\n{bullets(scope_out)}"


def spec_ref_block(spec_ref: object) -> str:
    if isinstance(spec_ref, str):
        ref = spec_ref.strip()
        return f"* {ref}" if ref else "* (none)"
    if isinstance(spec_ref, dict):
        path = str(spec_ref.get("path", "")).strip()
        if not path:
            return "* (none)"
        anchor = str(spec_ref.get("anchor", "")).strip()
        link = f"{path}#{anchor}" if anchor else path
        lines = [f"* {link}"]
        section = str(spec_ref.get("section", "")).strip()
        if section:
            lines.append(f"* Section: {section}")
        quote = str(spec_ref.get("quote", "")).strip()
        if quote:
            lines.append(f"* Quote: {quote}")
        return "\n".join(lines)
    return "* (none)"


def epic_body(epic: dict[str, object], plan_id: str, stories_list: str | None = None) -> str:
    stories_section = stories_list if stories_list is not None else "* (populated after stories are created)"
    return (
        f"""
<!-- PLAN_ID: {plan_id} -->

<!-- EPIC_ID: {epic["id"]} -->

## Goal

{epic.get("goal", "")}

## Scope

{scope_block(epic.get("scope", {}))}

## Success metrics

{bullets(epic.get("success_metrics", []))}

## Risks

{bullets(epic.get("risks", []))}

## Assumptions

{bullets(epic.get("assumptions", []))}

## Spec reference

{spec_ref_block(epic.get("spec_ref"))}

## Stories

{stories_section}
""".strip()
        + "\n"
    )


def story_body(story: dict[str, object], plan_id: str, epic_link: str, tasks_section: str | None = None) -> str:
    tasks_block = tasks_section if tasks_section is not None else "* (populated after tasks are created)"
    return (
        f"""
<!-- PLAN_ID: {plan_id} -->

<!-- STORY_ID: {story["id"]} -->

## Epic

* {epic_link}

## Goal

{story.get("goal", "")}

## Scope

{scope_block(story.get("scope", {}))}

## Success metrics

{bullets(story.get("success_metrics", []))}

## Risks

{bullets(story.get("risks", []))}

## Assumptions

{bullets(story.get("assumptions", []))}

## Spec reference

{spec_ref_block(story.get("spec_ref"))}

## Tasks

{tasks_block}
""".strip()
        + "\n"
    )


def task_body(task: dict[str, object], plan_id: str, story_link: str, dependencies_block: str) -> str:
    verification = task.get("verification", {}) if isinstance(task.get("verification", {}), dict) else {}
    commands = verification.get("commands", [])
    ci_checks = verification.get("ci_checks", [])
    evidence = verification.get("evidence", [])
    manual_steps = verification.get("manual_steps", [])
    manual_block = ""
    if manual_steps:
        manual_block = f"\n\nManual steps:\n\n{bullets(manual_steps)}"
    return (
        f"""
<!-- PLAN_ID: {plan_id} -->

<!-- TASK_ID: {task["id"]} -->

## Story

* {story_link}

## Motivation

{task.get("motivation", "")}

## Scope

{scope_block(task.get("scope", {}))}

## Requirements

{bullets(task.get("requirements", []))}

## Acceptance criteria

{bullets(task.get("acceptance_criteria", []))}

## Verification

Commands:\n\n{bullets(commands)}\n\nCI checks:\n\n{bullets(ci_checks)}\n\nEvidence:\n\n{bullets(evidence)}{manual_block}

## Artifacts

{bullets(task.get("artifacts", []))}

## Spec reference

{spec_ref_block(task.get("spec_ref"))}

## Dependencies

{dependencies_block}
""".strip()
        + "\n"
    )
