"""Label and issue-type helpers for GitHub provider."""

from __future__ import annotations

from typing import Any, cast

from planpilot.core.contracts.exceptions import ProviderCapabilityError, ProviderError
from planpilot.core.contracts.plan import PlanItemType


async def ensure_issue_type(provider: Any, issue_id: str, item_type: PlanItemType) -> None:  # pragma: no cover
    if not provider.context.supports_issue_type:
        raise ProviderCapabilityError("GitHub provider does not support issue types.", capability="issue-type")
    mapped_name = provider.context.create_type_map.get(item_type.value, item_type.value)
    issue_type_id = provider.context.issue_type_ids.get(mapped_name.upper()) or provider.context.issue_type_ids.get(
        item_type.value
    )
    if issue_type_id is None:
        raise ProviderError(f"Unable to resolve issue type id for {item_type.value}")
    client = provider._require_client()
    await client.update_issue(id=issue_id, issue_type_id=issue_type_id)


async def ensure_type_label(provider: Any, issue_id: str, item_type: PlanItemType) -> None:  # pragma: no cover
    mapped = provider.context.create_type_map.get(item_type.value)
    if mapped is None:
        raise ProviderError(f"No label mapping configured for {item_type.value}")
    await ensure_discovery_labels(provider, issue_id, [mapped])


async def ensure_discovery_labels(provider: Any, issue_id: str, labels: list[str]) -> None:  # pragma: no cover
    label_ids = await resolve_label_ids(provider, labels)
    if label_ids:
        client = provider._require_client()
        await client.add_labels(labelable_id=issue_id, label_ids=label_ids)


async def remove_labels_by_ids(provider: Any, issue_id: str, label_ids: list[str]) -> None:  # pragma: no cover
    if not label_ids:
        return
    client = provider._require_client()
    await client.remove_labels(labelable_id=issue_id, label_ids=label_ids)


async def resolve_label_ids(provider: Any, label_names: list[str]) -> list[str]:  # pragma: no cover
    ids: list[str] = []
    for name in label_names:
        if name == provider._label and provider.context.label_id:
            ids.append(provider.context.label_id)
        else:
            ids.append(await find_or_create_label(provider, name))
    return ids


async def find_or_create_label(provider: Any, name: str) -> str:  # pragma: no cover
    client = provider._require_client()
    owner, repo = provider._split_target()
    data = await client.find_labels(owner=owner, name=repo, query=name)
    if data.repository and data.repository.labels and data.repository.labels.nodes:
        for node in data.repository.labels.nodes:
            if node and node.name == name:
                return cast(str, node.id)
    return cast(str, await create_label(provider, provider.context.repo_id, name=name))


async def create_label(provider: Any, repo_id: str, *, name: str | None = None) -> str:  # pragma: no cover
    client = provider._require_client()
    data = await client.create_label(repository_id=repo_id, name=name or provider._label)
    if data.create_label is None or data.create_label.label is None:
        raise ProviderError("createLabel returned no label")
    return cast(str, data.create_label.label.id)
