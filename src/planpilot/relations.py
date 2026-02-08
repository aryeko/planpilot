from .github_api import gh_json
from .utils import build_blocked_by_map, build_parent_map


def fetch_issue_relation_maps(issue_ids: list[str]) -> dict[str, dict[str, str | None]]:
    parents: dict[str, str | None] = {}
    blocked_by: dict[str, set] = {}
    for i in range(0, len(issue_ids), 50):
        chunk = issue_ids[i : i + 50]
        ids = ",".join([f'"{cid}"' for cid in chunk])
        query = f"""
        query {{
          nodes(ids: [{ids}]) {{
            ... on Issue {{
              id
              parent {{ id }}
              blockedBy(first:100) {{ nodes {{ id }} }}
            }}
          }}
        }}
        """
        data = gh_json(["api", "graphql", "-f", f"query={query}"])
        nodes = data.get("data", {}).get("nodes", []) if data else []
        parents.update(build_parent_map(nodes))
        blocked_by.update(build_blocked_by_map(nodes))
    return {"parents": parents, "blocked_by": blocked_by}


def add_blocked_by(issue_id: str, blocked_by_issue_id: str, blocked_by_map: dict[str, set]) -> int:
    blocked_set = blocked_by_map.get(issue_id, set())
    if blocked_by_issue_id in blocked_set:
        return 0
    query = """
    mutation($issueId:ID!, $blockingIssueId:ID!) {
      addBlockedBy(input:{issueId:$issueId, blockingIssueId:$blockingIssueId}) {
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
            f"issueId={issue_id}",
            "-f",
            f"blockingIssueId={blocked_by_issue_id}",
        ]
    )
    blocked_set.add(blocked_by_issue_id)
    blocked_by_map[issue_id] = blocked_set
    return 1
