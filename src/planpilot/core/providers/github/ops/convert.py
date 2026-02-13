"""Conversion and parsing helpers for GitHub provider."""

from __future__ import annotations

from typing import TYPE_CHECKING

from planpilot.core.contracts.exceptions import ProviderError
from planpilot.core.providers.github.github_gql.fragments import IssueCore
from planpilot.core.providers.github.item import GitHubItem

if TYPE_CHECKING:
    from planpilot.core.providers.github.provider import GitHubProvider


def item_from_issue_core(provider: GitHubProvider, issue: IssueCore) -> GitHubItem:
    labels_nodes = issue.labels.nodes if issue.labels is not None and issue.labels.nodes is not None else []
    labels = [node.name for node in labels_nodes if node and node.name]
    return GitHubItem(
        provider=provider,
        issue_id=issue.id,
        number=issue.number,
        title=issue.title,
        body=issue.body,
        item_type=None,
        url=issue.url,
        labels=labels,
    )


def split_target(target: str) -> tuple[str, str]:
    parts = target.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ProviderError(f"Invalid target '{target}'. Expected owner/repo.")
    return parts[0], parts[1]
