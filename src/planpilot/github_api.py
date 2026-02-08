import json
import subprocess
from typing import Any


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    res = subprocess.run(cmd, text=True, capture_output=True)
    if check and res.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{res.stderr}")
    return res


def gh_json(args: list[str]) -> Any:
    res = run(["gh", *args])
    if res.stdout.strip() == "":
        return None
    return json.loads(res.stdout)


def gh_run(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return run(["gh", *args], check=check)


def search_issues_by_plan_id(repo: str, query_str: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    cursor = None
    query = """
    query($searchQuery:String!, $after:String) {
      search(query:$searchQuery, type:ISSUE, first:100, after:$after) {
        nodes {
          ... on Issue { id number body }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
    """
    while True:
        args = ["api", "graphql", "-f", f"query={query}", "-f", f"searchQuery={query_str}"]
        if cursor:
            args += ["-f", f"after={cursor}"]
        data = gh_json(args)
        search = data.get("data", {}).get("search") if data else None
        nodes = search.get("nodes", []) if search else []
        results.extend(nodes)
        page = search.get("pageInfo") if search else None
        if not page or not page.get("hasNextPage"):
            break
        cursor = page.get("endCursor")
    return results


def create_issue(repo_id: str, input_value: dict[str, Any]) -> dict[str, Any] | None:
    if not repo_id:
        return None
    query = """
    mutation($input:CreateIssueInput!) {
      createIssue(input:$input) {
        issue { id number url }
      }
    }
    """
    args = ["api", "graphql", "-f", f"query={query}"]
    for key, value in input_value.items():
        if isinstance(value, list):
            for item in value:
                args += ["-F", f"input[{key}][]={item}"]
        else:
            args += ["-F", f"input[{key}]={value}"]
    data = gh_json(args)
    return data.get("data", {}).get("createIssue", {}).get("issue") if data else None


def fetch_project_items(project_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    after = None
    while True:
        q = """
        query($projectId:ID!, $after:String) {
          node(id:$projectId) {
            ... on ProjectV2 {
              items(first:100, after:$after) {
                nodes { id content { ... on Issue { id } } }
                pageInfo { hasNextPage endCursor }
              }
            }
          }
        }
        """
        args = ["api", "graphql", "-f", f"query={q}", "-f", f"projectId={project_id}"]
        if after:
            args += ["-f", f"after={after}"]
        data = gh_json(args)
        items_page = data["data"]["node"]["items"]["nodes"] if data else []
        items.extend(items_page)
        page = data["data"]["node"]["items"]["pageInfo"] if data else None
        if not page or not page.get("hasNextPage"):
            break
        after = page.get("endCursor")
    return items


def add_project_item(project_id: str, content_id: str) -> str | None:
    query = """
    mutation($projectId:ID!, $contentId:ID!) {
      addProjectV2ItemById(input:{projectId:$projectId, contentId:$contentId}) {
        item { id }
      }
    }
    """
    data = gh_json(
        ["api", "graphql", "-f", f"query={query}", "-f", f"projectId={project_id}", "-f", f"contentId={content_id}"]
    )
    return data["data"]["addProjectV2ItemById"]["item"]["id"] if data else None


def update_project_field(project_id: str, item_id: str, field_id: str, value: dict[str, Any]) -> None:
    query = """
    mutation($projectId:ID!, $itemId:ID!, $fieldId:ID!, $value:ProjectV2FieldValue!) {
      updateProjectV2ItemFieldValue(input:{
        projectId:$projectId,
        itemId:$itemId,
        fieldId:$fieldId,
        value:$value
      }) {
        projectV2Item { id }
      }
    }
    """
    if len(value) != 1:
        raise ValueError("Project field value must contain exactly one key")
    key, val = next(iter(value.items()))
    gh_json(
        [
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-F",
            f"projectId={project_id}",
            "-F",
            f"itemId={item_id}",
            "-F",
            f"fieldId={field_id}",
            "-F",
            f"value[{key}]={val}",
        ]
    )
