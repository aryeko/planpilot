def parse_markers(body: str) -> dict[str, str]:
    def extract(label: str) -> str:
        token = f"<!-- {label}:"
        start = body.find(token)
        if start == -1:
            return ""
        end = body.find("-->", start)
        if end == -1:
            return ""
        return body[start + len(token) : end].strip()

    return {
        "plan_id": extract("PLAN_ID"),
        "epic_id": extract("EPIC_ID"),
        "story_id": extract("STORY_ID"),
        "task_id": extract("TASK_ID"),
    }


def build_issue_mapping(issues: list, plan_id: str = "") -> dict[str, dict[str, dict[str, int]]]:
    mapping = {"epics": {}, "stories": {}, "tasks": {}}
    for issue in issues:
        markers = parse_markers(issue.get("body", ""))
        if plan_id and markers.get("plan_id") != plan_id:
            continue
        epic_id = markers.get("epic_id")
        story_id = markers.get("story_id")
        task_id = markers.get("task_id")
        if epic_id:
            mapping["epics"][epic_id] = {"id": issue.get("id"), "number": issue.get("number")}
        if story_id:
            mapping["stories"][story_id] = {"id": issue.get("id"), "number": issue.get("number")}
        if task_id:
            mapping["tasks"][task_id] = {"id": issue.get("id"), "number": issue.get("number")}
    return mapping


def build_issue_search_query(repo: str, plan_id: str) -> str:
    return f'repo:{repo} is:issue in:body "PLAN_ID: {plan_id}"'


def build_create_issue_input(repo_id: str, title: str, body: str, label_ids: list) -> dict[str, object]:
    payload = {
        "repositoryId": repo_id,
        "title": title,
        "body": body,
    }
    if label_ids:
        payload["labelIds"] = label_ids
    return payload


def build_project_item_map(items: list) -> dict[str, str]:
    cache = {}
    for item in items:
        content = item.get("content") or {}
        content_id = content.get("id")
        if content_id and item.get("id"):
            cache[content_id] = item["id"]
    return cache


def get_project_item_id(content_id: str, cache: dict[str, str]) -> str | None:
    return cache.get(content_id)


def build_task_dependencies_block(dep_ids: dict[str, str]) -> str:
    if not dep_ids:
        return "Blocked by:\n\n* (none)"
    items = "\n".join([f"* {value}" for value in dep_ids.values()])
    return f"Blocked by:\n\n{items}"


def build_epic_stories_section(items: list) -> str:
    if not items:
        return "* (none)"
    lines = [f"* [ ] #{number} {title}" for number, title in items]
    return "\n".join(lines)


def build_story_tasks_section(items: list) -> str:
    if not items:
        return "* (none)"
    lines = [f"* [ ] #{number} {title}" for number, title in items]
    return "\n".join(lines)


def build_parent_map(nodes: list) -> dict[str, str | None]:
    mapping = {}
    for node in nodes:
        parent = node.get("parent")
        mapping[node.get("id")] = parent.get("id") if parent else None
    return mapping


def build_blocked_by_map(nodes: list) -> dict[str, set]:
    mapping = {}
    for node in nodes:
        blocked = node.get("blockedBy", {}).get("nodes", [])
        mapping[node.get("id")] = {n.get("id") for n in blocked if n.get("id")}
    return mapping


def resolve_option_id(options: list, name: str) -> str | None:
    if not name:
        return None
    for opt in options:
        if opt.get("name", "").lower() == name.lower():
            return opt.get("id")
    return None
