"""Conversion and parsing helpers for GitHub provider."""

from __future__ import annotations

from typing import Any

from planpilot.core.contracts.exceptions import ProviderError
from planpilot.core.contracts.plan import PlanItemType
from planpilot.core.metadata import parse_metadata_block
from planpilot.core.providers.github.github_gql.fragments import IssueCore
from planpilot.core.providers.github.item import GitHubItem


def item_from_issue_core(provider: Any, issue: IssueCore) -> GitHubItem:
    labels_nodes = issue.labels.nodes if issue.labels is not None and issue.labels.nodes is not None else []
    labels = [node.name for node in labels_nodes if node and node.name]
    metadata = parse_metadata_block(issue.body or "")
    item_type_raw = metadata.get("ITEM_TYPE")
    item_type = None
    if item_type_raw is not None:
        try:
            item_type = PlanItemType(item_type_raw)
        except ValueError:
            item_type = None
    return GitHubItem(
        provider=provider,
        issue_id=issue.id,
        number=issue.number,
        title=issue.title,
        body=issue.body,
        item_type=item_type,
        url=issue.url,
        labels=labels,
    )


def split_target(target: str) -> tuple[str, str]:
    parts = target.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ProviderError(f"Invalid target '{target}'. Expected owner/repo.")
    return parts[0], parts[1]
