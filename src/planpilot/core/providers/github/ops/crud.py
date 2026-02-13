"""CRUD helpers for GitHub provider."""

from __future__ import annotations

import logging
from typing import Any, cast

from planpilot.core.contracts.exceptions import ProviderError
from planpilot.core.contracts.item import CreateItemInput, UpdateItemInput
from planpilot.core.providers.github.github_gql.fragments import IssueCore
from planpilot.core.providers.github.github_gql.search_issues import SearchIssuesSearchNodesIssue

_LOG = logging.getLogger(__name__)


async def search_issue_nodes(provider: Any, query: str) -> list[IssueCore]:  # pragma: no cover
    client = provider._require_client()
    cursor: str | None = None
    nodes: list[IssueCore] = []
    pages = 0
    while True:
        pages += 1
        if pages > 100:
            raise ProviderError("Discovery pagination exceeded safety budget.")
        data = await client.search_issues(query=query, cursor=cursor)
        search = data.search
        if search.nodes:
            for node in search.nodes:
                if isinstance(node, SearchIssuesSearchNodesIssue):
                    nodes.append(node)
        if not search.page_info.has_next_page:
            break
        cursor = search.page_info.end_cursor
    return nodes


async def create_issue(provider: Any, input: CreateItemInput) -> IssueCore:  # pragma: no cover
    client = provider._require_client()

    all_labels = list(dict.fromkeys([provider._label, *input.labels]))
    if provider.context.create_type_strategy == "label":
        type_label = provider.context.create_type_map.get(input.item_type.value)
        if type_label:
            all_labels = list(dict.fromkeys([*all_labels, type_label]))
    label_ids = await provider._resolve_label_ids(all_labels)

    issue_type_id: str | None = None
    if provider.context.create_type_strategy == "issue-type":
        mapped_name = provider.context.create_type_map.get(input.item_type.value, input.item_type.value)
        issue_type_id = provider.context.issue_type_ids.get(mapped_name.upper()) or provider.context.issue_type_ids.get(
            input.item_type.value
        )
        if issue_type_id is None:
            _LOG.warning("Could not resolve issue type ID for %r; issue created without a type", mapped_name)

    project_ids = [provider.context.project_id] if provider.context.project_id else None

    data = await client.create_issue(
        repository_id=provider.context.repo_id,
        title=input.title,
        body=input.body,
        label_ids=label_ids or None,
        issue_type_id=issue_type_id,
        project_v_2_ids=project_ids,
    )

    if data.create_issue is None or data.create_issue.issue is None:
        raise ProviderError("createIssue returned no issue")
    return cast(IssueCore, data.create_issue.issue)


async def update_issue(provider: Any, item_id: str, input: UpdateItemInput) -> IssueCore:  # pragma: no cover
    client = provider._require_client()

    issue_type_id: str | None = None
    if input.item_type is not None and provider.context.create_type_strategy == "issue-type":
        mapped_name = provider.context.create_type_map.get(input.item_type.value, input.item_type.value)
        issue_type_id = provider.context.issue_type_ids.get(mapped_name.upper()) or provider.context.issue_type_ids.get(
            input.item_type.value
        )
        if issue_type_id is None:
            _LOG.warning("Could not resolve issue type ID for %r; issue type will not be updated", mapped_name)

    data = await client.update_issue(
        id=item_id,
        title=input.title,
        body=input.body,
        issue_type_id=issue_type_id,
    )

    if data.update_issue is None or data.update_issue.issue is None:
        raise ProviderError("updateIssue returned no issue")
    return cast(IssueCore, data.update_issue.issue)


async def get_issue(provider: Any, item_id: str) -> IssueCore:  # pragma: no cover
    client = provider._require_client()
    from planpilot.core.providers.github.github_gql.get_issue import GetIssueNodeIssue

    data = await client.get_issue(id=item_id)
    if data.node is None or not isinstance(data.node, GetIssueNodeIssue):
        raise ProviderError(f"Issue not found: {item_id}")
    return cast(IssueCore, data.node)


async def get_item_labels(provider: Any, item_id: str) -> list[str]:  # pragma: no cover
    issue = await provider._get_issue(item_id)
    if issue.labels and issue.labels.nodes:
        return [n.name for n in issue.labels.nodes if n]
    return []
