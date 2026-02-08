import hashlib
import json
import sys
from pathlib import Path

from .body_render import epic_body, story_body, task_body
from .github_api import (
    add_project_item,
    create_issue,
    fetch_project_items,
    gh_json,
    gh_run,
    search_issues_by_plan_id,
    update_project_field,
)
from .project_fields import resolve_project_fields
from .relations import add_blocked_by, fetch_issue_relation_maps
from .types import SyncConfig
from .utils import (
    build_create_issue_input,
    build_epic_stories_section,
    build_issue_mapping,
    build_issue_search_query,
    build_project_item_map,
    build_story_tasks_section,
    build_task_dependencies_block,
    get_project_item_id,
    resolve_option_id,
)

# Module-level state for logging
_verbose = False
_dry_run = False


def _log(msg: str) -> None:
    """Log a message if verbose mode is enabled."""
    if _verbose:
        print(f"[sync] {msg}", file=sys.stderr)


def _log_dry(action: str, details: str) -> None:
    """Log a dry-run action."""
    if _dry_run:
        print(f"[dry-run] {action}: {details}")
    elif _verbose:
        print(f"[sync] {action}: {details}", file=sys.stderr)


def run_sync(config: SyncConfig) -> None:
    global _verbose, _dry_run
    _verbose = config.verbose
    _dry_run = config.dry_run

    if _dry_run:
        print("[dry-run] No changes will be made to GitHub")

    _log(f"Loading plan from {config.epics_path}, {config.stories_path}, {config.tasks_path}")

    for p in [config.epics_path, config.stories_path, config.tasks_path]:
        if not Path(p).exists():
            raise RuntimeError(f"missing required file: {p}")

    try:
        epics = json.loads(Path(config.epics_path).read_text())
        stories = json.loads(Path(config.stories_path).read_text())
        tasks = json.loads(Path(config.tasks_path).read_text())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON input: {exc}") from exc

    auth = gh_run(["auth", "status"], check=False)
    if auth.returncode != 0:
        raise RuntimeError("GitHub authentication failed. Run `gh auth login` and retry.")

    # validation
    epic_ids = {e["id"] for e in epics}
    story_ids = {s["id"] for s in stories}
    story_ids_in_order = [s["id"] for s in stories]
    task_ids = {t["id"] for t in tasks}
    errors: list[str] = []
    if len(epics) != 1:
        errors.append("plan must contain exactly one epic")

    story_tasks: dict[str, list[str]] = {sid: [] for sid in story_ids}
    for task in tasks:
        story_id = task.get("story_id")
        if story_id not in story_ids:
            errors.append(f"task {task.get('id')} story_id {story_id} not found in stories")
            continue
        story_tasks.setdefault(story_id, []).append(task.get("id"))
        for dep in task.get("depends_on", []):
            if dep not in task_ids:
                errors.append(f"task {task.get('id')} depends_on {dep} not found in tasks")

    for story in stories:
        epic_id = story.get("epic_id") or (epics[0].get("id") if epics else None)
        if epic_id not in epic_ids:
            errors.append(f"story {story.get('id')} epic_id {epic_id} not found in epics")
        task_list = story.get("task_ids") or story.get("story_ids") or []
        if task_list:
            missing = [tid for tid in task_list if tid not in task_ids]
            if missing:
                errors.append(f"story {story.get('id')} references unknown task_ids {missing}")
            extras = set(story_tasks.get(story.get("id"), [])) - set(task_list)
            if extras:
                errors.append(f"story {story.get('id')} missing task_ids for {sorted(extras)}")
        if (
            story.get("task_ids") is None
            and story.get("story_ids") is None
            and story_tasks.get(story.get("id"), []) == []
        ):
            errors.append(f"story {story.get('id')} has no tasks")

    if epics:
        epic = epics[0]
        epic_story_ids = epic.get("story_ids") or []
        missing_stories = [sid for sid in epic_story_ids if sid not in story_ids]
        if missing_stories:
            errors.append(f"epic {epic.get('id')} references unknown story_ids {missing_stories}")
        if epic_story_ids:
            extras = set(story_ids) - set(epic_story_ids)
            if extras:
                errors.append(f"epic {epic.get('id')} missing story_ids for {sorted(extras)}")
    if errors:
        raise RuntimeError("Validation errors:\n" + "\n".join(errors))

    norm = json.dumps({"epics": epics, "stories": stories, "tasks": tasks}, sort_keys=True, separators=(",", ":"))
    plan_id = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:12]

    # project
    project_id = None
    project_fields = None
    project_item_map: dict[str, str] = {}
    try:
        org = config.project_url.split("/orgs/")[1].split("/projects/")[0]
        number = int(config.project_url.rstrip("/").split("/projects/")[1])
        query = """
        query($org:String!, $number:Int!) {
          organization(login:$org) {
            projectV2(number:$number) {
              id
              fields(first:100) {
                nodes {
                  ... on ProjectV2FieldCommon { id name }
                  ... on ProjectV2SingleSelectField { id name options { id name } }
                  ... on ProjectV2IterationField {
                    id name configuration { iterations { id title startDate duration } }
                  }
                }
              }
            }
          }
        }
        """
        data = gh_json(["api", "graphql", "-f", f"query={query}", "-f", f"org={org}", "-F", f"number={number}"])
        project = data["data"]["organization"]["projectV2"] if data else None
        project_id = project.get("id") if project else None
        if project:
            project_fields = resolve_project_fields(
                project, config.status, config.priority, config.iteration, config.size_field
            )
            project_item_map = build_project_item_map(fetch_project_items(project_id))
    except Exception:
        project_id = None

    # repo id + label id + issue types
    issue_type_ids: dict[str, str] = {}
    repo_id = None
    label_id = None
    try:
        owner, repo_name = config.repo.split("/", 1)
        query = """
        query($owner:String!, $name:String!, $label:String!) {
          repository(owner:$owner, name:$name) {
            id
            issueTypes(first:100) { nodes { id name } }
            labels(query:$label, first:1) { nodes { id name } }
          }
        }
        """
        data = gh_json(
            [
                "api",
                "graphql",
                "-f",
                f"query={query}",
                "-f",
                f"owner={owner}",
                "-f",
                f"name={repo_name}",
                "-f",
                f"label={config.label}",
            ]
        )
        repo = data["data"]["repository"] if data else None
        issue_type_ids = {n["name"]: n["id"] for n in repo["issueTypes"]["nodes"]} if repo else {}
        repo_id = repo.get("id") if repo else None
        label_nodes = repo.get("labels", {}).get("nodes", []) if repo else []
        label_id = label_nodes[0]["id"] if label_nodes else None
    except Exception:
        pass

    # ensure label via gh if missing
    if label_id is None:
        labels = gh_json(["label", "list", "-R", config.repo, "--limit", "100", "--json", "name"]) or []
        names = {lbl["name"] for lbl in labels}
        if config.label not in names:
            if _dry_run:
                _log_dry("create label", config.label)
            else:
                _log(f"Creating label: {config.label}")
                gh_run(
                    [
                        "label",
                        "create",
                        config.label,
                        "-R",
                        config.repo,
                        "--description",
                        f"{config.label} tracking issue",
                        "--color",
                        "0E8A16",
                    ]
                )
        # try again
        if repo_id:
            owner, repo_name = config.repo.split("/", 1)
            query = """
            query($owner:String!, $name:String!, $label:String!) {
              repository(owner:$owner, name:$name) {
                labels(query:$label, first:1) { nodes { id name } }
              }
            }
            """
            data = gh_json(
                [
                    "api",
                    "graphql",
                    "-f",
                    f"query={query}",
                    "-f",
                    f"owner={owner}",
                    "-f",
                    f"name={repo_name}",
                    "-f",
                    f"label={config.label}",
                ]
            )
            repo = data["data"]["repository"] if data else None
            label_nodes = repo.get("labels", {}).get("nodes", []) if repo else []
            label_id = label_nodes[0]["id"] if label_nodes else None

    # existing issues
    query_str = build_issue_search_query(config.repo, plan_id)
    existing = search_issues_by_plan_id(config.repo, query_str)
    existing_map = build_issue_mapping(existing, plan_id=plan_id)

    sync_map = {
        "plan_id": plan_id,
        "repo": config.repo,
        "project_url": config.project_url,
        "epics": {},
        "stories": {},
        "tasks": {},
    }

    def set_project_fields(item_id: str, size_option_id: str | None = None) -> None:
        if not project_id or not project_fields:
            return
        if project_fields.status_field_id and project_fields.status_option_id:
            update_project_field(
                project_id,
                item_id,
                project_fields.status_field_id,
                {
                    "singleSelectOptionId": project_fields.status_option_id,
                },
            )
        if project_fields.priority_field_id and project_fields.priority_option_id:
            update_project_field(
                project_id,
                item_id,
                project_fields.priority_field_id,
                {
                    "singleSelectOptionId": project_fields.priority_option_id,
                },
            )
        if project_fields.iteration_field_id and project_fields.iteration_option_id:
            update_project_field(
                project_id,
                item_id,
                project_fields.iteration_field_id,
                {
                    "iterationId": project_fields.iteration_option_id,
                },
            )
        if project_fields.size_field_id and size_option_id:
            update_project_field(
                project_id,
                item_id,
                project_fields.size_field_id,
                {
                    "singleSelectOptionId": size_option_id,
                },
            )

    def add_to_project(issue_id: str) -> str | None:
        if not project_id:
            return None
        existing_item = get_project_item_id(issue_id, project_item_map)
        if existing_item:
            return existing_item
        item_id = add_project_item(project_id, issue_id)
        if item_id:
            project_item_map[issue_id] = item_id
        return item_id

    story_by_id = {story["id"]: story for story in stories}
    task_by_id = {task["id"]: task for task in tasks}

    # upsert epic
    for epic in epics:
        existing_epic = existing_map["epics"].get(epic["id"])
        issue_number = existing_epic["number"] if existing_epic else None
        issue_id = existing_epic["id"] if existing_epic else None
        issue_url = None
        if not issue_number:
            body = epic_body(epic, plan_id)
            input_value = build_create_issue_input(repo_id, epic["title"], body, [label_id] if label_id else [])
            if _dry_run:
                _log_dry("create epic issue", f"{epic['id']}: {epic['title']}")
                issue_number = 0
                issue_id = f"dry-run-epic-{epic['id']}"
                issue_url = f"https://github.com/{config.repo}/issues/DRY-RUN"
            else:
                _log(f"Creating epic issue: {epic['title']}")
                created = create_issue(repo_id, input_value)
                if created:
                    issue_number = created.get("number")
                    issue_id = created.get("id")
                    issue_url = created.get("url")
                else:
                    raise RuntimeError(f"Failed to create epic issue for {epic['id']}")
        if issue_id and issue_type_ids.get("Epic") and not _dry_run:
            query = """
            mutation($id:ID!, $issueTypeId:ID!) {
              updateIssue(input:{id:$id, issueTypeId:$issueTypeId}) { issue { id } }
            }
            """
            gh_json(
                [
                    "api",
                    "graphql",
                    "-f",
                    f"query={query}",
                    "-f",
                    f"id={issue_id}",
                    "-f",
                    f"issueTypeId={issue_type_ids['Epic']}",
                ]
            )
        item_id = None if _dry_run else add_to_project(issue_id)
        if item_id:
            set_project_fields(item_id)
        sync_map["epics"][epic["id"]] = {
            "issue_number": issue_number,
            "url": issue_url or f"https://github.com/{config.repo}/issues/{issue_number}",
            "node_id": issue_id,
            "project_item_id": item_id,
        }

    # upsert stories
    for story in stories:
        existing_story = existing_map["stories"].get(story["id"])
        issue_number = existing_story["number"] if existing_story else None
        issue_id = existing_story["id"] if existing_story else None
        issue_url = None
        epic_id = story.get("epic_id") or (epics[0].get("id") if epics else None)
        epic_issue = sync_map["epics"][epic_id]["issue_number"]
        epic_link = f"#{epic_issue}"
        if not issue_number:
            body = story_body(story, plan_id, epic_link)
            input_value = build_create_issue_input(repo_id, story["title"], body, [label_id] if label_id else [])
            if _dry_run:
                _log_dry("create story issue", f"{story['id']}: {story['title']}")
                issue_number = 0
                issue_id = f"dry-run-story-{story['id']}"
                issue_url = f"https://github.com/{config.repo}/issues/DRY-RUN"
            else:
                _log(f"Creating story issue: {story['title']}")
                created = create_issue(repo_id, input_value)
                if created:
                    issue_number = created.get("number")
                    issue_id = created.get("id")
                    issue_url = created.get("url")
                else:
                    raise RuntimeError(f"Failed to create story issue for {story['id']}")
        if issue_id and issue_type_ids.get("Story") and not _dry_run:
            query = """
            mutation($id:ID!, $issueTypeId:ID!) {
              updateIssue(input:{id:$id, issueTypeId:$issueTypeId}) { issue { id } }
            }
            """
            gh_json(
                [
                    "api",
                    "graphql",
                    "-f",
                    f"query={query}",
                    "-f",
                    f"id={issue_id}",
                    "-f",
                    f"issueTypeId={issue_type_ids['Story']}",
                ]
            )
        item_id = None if _dry_run else add_to_project(issue_id)
        if item_id:
            set_project_fields(item_id)
        sync_map["stories"][story["id"]] = {
            "issue_number": issue_number,
            "url": issue_url or f"https://github.com/{config.repo}/issues/{issue_number}",
            "node_id": issue_id,
            "project_item_id": item_id,
        }

    # upsert tasks
    for task in tasks:
        existing_task = existing_map["tasks"].get(task["id"])
        issue_number = existing_task["number"] if existing_task else None
        issue_id = existing_task["id"] if existing_task else None
        issue_url = None
        story_issue = sync_map["stories"][task["story_id"]]["issue_number"]
        story_link = f"#{story_issue}"
        if not issue_number:
            body = task_body(task, plan_id, story_link, "Blocked by:\n\n* (populated after mapping exists)")
            input_value = build_create_issue_input(repo_id, task["title"], body, [label_id] if label_id else [])
            if _dry_run:
                _log_dry("create task issue", f"{task['id']}: {task['title']}")
                issue_number = 0
                issue_id = f"dry-run-task-{task['id']}"
                issue_url = f"https://github.com/{config.repo}/issues/DRY-RUN"
            else:
                _log(f"Creating task issue: {task['title']}")
                created = create_issue(repo_id, input_value)
                if created:
                    issue_number = created.get("number")
                    issue_id = created.get("id")
                    issue_url = created.get("url")
                else:
                    raise RuntimeError(f"Failed to create task issue for {task['id']}")
        if issue_id and issue_type_ids.get("Task") and not _dry_run:
            query = """
            mutation($id:ID!, $issueTypeId:ID!) {
              updateIssue(input:{id:$id, issueTypeId:$issueTypeId}) { issue { id } }
            }
            """
            gh_json(
                [
                    "api",
                    "graphql",
                    "-f",
                    f"query={query}",
                    "-f",
                    f"id={issue_id}",
                    "-f",
                    f"issueTypeId={issue_type_ids['Task']}",
                ]
            )
        item_id = None if _dry_run else add_to_project(issue_id)
        if item_id:
            size_option_id = None
            if config.size_field and config.size_from_tshirt:
                estimate = task.get("estimate", {}) if isinstance(task.get("estimate", {}), dict) else {}
                tshirt = estimate.get("tshirt")
                size_option_id = resolve_option_id(project_fields.size_options if project_fields else [], tshirt)
            set_project_fields(item_id, size_option_id=size_option_id)
        sync_map["tasks"][task["id"]] = {
            "issue_number": issue_number,
            "url": issue_url or f"https://github.com/{config.repo}/issues/{issue_number}",
            "node_id": issue_id,
            "project_item_id": item_id,
        }

    # final bodies + relations
    if _dry_run:
        _log_dry("update issue bodies", f"{len(tasks)} tasks, {len(stories)} stories, {len(epics)} epics")
        _log_dry("link sub-issues", "stories under epic, tasks under stories")
        _log_dry("add blocked-by links", "task dependencies")
        parent_map = {}
        blocked_by_map = {}
    else:
        relation_ids = (
            [data["node_id"] for data in sync_map["tasks"].values()]
            + [data["node_id"] for data in sync_map["stories"].values()]
            + [data["node_id"] for data in sync_map["epics"].values()]
        )
        relation_maps = fetch_issue_relation_maps(relation_ids)
        parent_map = relation_maps["parents"]
        blocked_by_map = relation_maps["blocked_by"]

        # update task bodies with dependencies
        for task in tasks:
            story_issue = sync_map["stories"][task["story_id"]]["issue_number"]
            story_link = f"#{story_issue}"
            deps = {dep: f"#{sync_map['tasks'][dep]['issue_number']}" for dep in task.get("depends_on", [])}
            dep_block = build_task_dependencies_block(deps)
            body = task_body(task, plan_id, story_link, dep_block)
            issue_number = sync_map["tasks"][task["id"]]["issue_number"]
            _log(f"Updating task issue #{issue_number}")
            gh_run(["issue", "edit", "-R", config.repo, str(issue_number), "--title", task["title"], "--body", body])

        # update story bodies with tasks list
        for story in stories:
            epic_id = story.get("epic_id") or (epics[0].get("id") if epics else None)
            epic_issue = sync_map["epics"][epic_id]["issue_number"]
            epic_link = f"#{epic_issue}"
            task_items = []
            task_ids_for_story = story.get("task_ids") or story.get("story_ids") or story_tasks.get(story["id"], [])
            for tid in task_ids_for_story:
                tdata = sync_map["tasks"].get(tid)
                if tdata:
                    task = task_by_id[tid]
                    task_items.append((tdata["issue_number"], task["title"]))
            tasks_list = build_story_tasks_section(task_items)
            body = story_body(story, plan_id, epic_link, tasks_section=tasks_list)
            issue_number = sync_map["stories"][story["id"]]["issue_number"]
            _log(f"Updating story issue #{issue_number}")
            gh_run(["issue", "edit", "-R", config.repo, str(issue_number), "--title", story["title"], "--body", body])

        # update epic bodies with stories list
        for epic in epics:
            story_items = []
            story_ids_for_epic = epic.get("story_ids") or story_ids_in_order
            for sid in story_ids_for_epic:
                sdata = sync_map["stories"].get(sid)
                if sdata:
                    story = story_by_id[sid]
                    story_items.append((sdata["issue_number"], story["title"]))
            stories_list = build_epic_stories_section(story_items)
            body = epic_body(epic, plan_id, stories_list=stories_list)
            issue_number = sync_map["epics"][epic["id"]]["issue_number"]
            _log(f"Updating epic issue #{issue_number}")
            gh_run(["issue", "edit", "-R", config.repo, str(issue_number), "--title", epic["title"], "--body", body])

    if not _dry_run:
        # blocked-by links for tasks
        for task in tasks:
            task_node_id = sync_map["tasks"][task["id"]]["node_id"]
            for dep in task.get("depends_on", []):
                dep_node_id = sync_map["tasks"][dep]["node_id"]
                add_blocked_by(task_node_id, dep_node_id, blocked_by_map)

        # roll up blocked-by to stories
        story_blocked_by = set()
        task_story = {t["id"]: t["story_id"] for t in tasks}
        for task in tasks:
            for dep in task.get("depends_on", []):
                story_id = task_story.get(task["id"])
                dep_story_id = task_story.get(dep)
                if story_id and dep_story_id and story_id != dep_story_id:
                    story_blocked_by.add((story_id, dep_story_id))

        for story_id, blocked_by_story_id in sorted(story_blocked_by):
            story_node_id = sync_map["stories"][story_id]["node_id"]
            blocked_by_node_id = sync_map["stories"][blocked_by_story_id]["node_id"]
            add_blocked_by(story_node_id, blocked_by_node_id, blocked_by_map)

        # roll up blocked-by to epic if multiple epics exist
        epic_blocked_by = set()
        story_epic = {s["id"]: (s.get("epic_id") or (epics[0].get("id") if epics else None)) for s in stories}
        for story_id, blocked_by_story_id in sorted(story_blocked_by):
            epic_id = story_epic.get(story_id)
            blocked_by_epic_id = story_epic.get(blocked_by_story_id)
            if epic_id and blocked_by_epic_id and epic_id != blocked_by_epic_id:
                epic_blocked_by.add((epic_id, blocked_by_epic_id))

        for epic_id, blocked_by_epic_id in sorted(epic_blocked_by):
            epic_node_id = sync_map["epics"][epic_id]["node_id"]
            blocked_by_node_id = sync_map["epics"][blocked_by_epic_id]["node_id"]
            add_blocked_by(epic_node_id, blocked_by_node_id, blocked_by_map)

        # sub-issues: stories under epic
        for story in stories:
            epic_id = story.get("epic_id") or (epics[0].get("id") if epics else None)
            epic_node_id = sync_map["epics"][epic_id]["node_id"]
            story_node_id = sync_map["stories"][story["id"]]["node_id"]
            parent_id = parent_map.get(story_node_id)
            if parent_id:
                if parent_id != epic_node_id:
                    raise RuntimeError(f"Sub-issue parent mismatch for story {story['id']}")
                continue
            _log(f"Linking story {story['id']} as sub-issue of epic")
            query = """
            mutation($issueId:ID!, $subIssueId:ID!) {
              addSubIssue(input:{issueId:$issueId, subIssueId:$subIssueId}) {
                issue { id }
              }
            }
            """
            gh_json(
                [
                    "api",
                    "graphql",
                    "-f",
                    f"query={query}",
                    "-f",
                    f"issueId={epic_node_id}",
                    "-f",
                    f"subIssueId={story_node_id}",
                ]
            )

        # sub-issues: tasks under stories
        for task in tasks:
            story_node_id = sync_map["stories"][task["story_id"]]["node_id"]
            task_node_id = sync_map["tasks"][task["id"]]["node_id"]
            parent_id = parent_map.get(task_node_id)
            if parent_id:
                if parent_id != story_node_id:
                    raise RuntimeError(f"Sub-issue parent mismatch for task {task['id']}")
                continue
            _log(f"Linking task {task['id']} as sub-issue of story")
            query = """
            mutation($issueId:ID!, $subIssueId:ID!) {
              addSubIssue(input:{issueId:$issueId, subIssueId:$subIssueId}) {
                issue { id }
              }
            }
            """
            gh_json(
                [
                    "api",
                    "graphql",
                    "-f",
                    f"query={query}",
                    "-f",
                    f"issueId={story_node_id}",
                    "-f",
                    f"subIssueId={task_node_id}",
                ]
            )

    # Write sync map (even in dry-run for inspection)
    if _dry_run:
        _log_dry("write sync map", config.sync_path)
    Path(config.sync_path).write_text(json.dumps(sync_map, indent=2))

    # Summary
    print(f"\nSync complete: {len(epics)} epic(s), {len(stories)} story(s), {len(tasks)} task(s)")
    if _dry_run:
        print("[dry-run] No changes were made to GitHub")
