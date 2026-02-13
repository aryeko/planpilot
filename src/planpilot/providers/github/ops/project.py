"""Project context/field helpers for GitHub provider."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from planpilot.contracts.exceptions import ProviderError
from planpilot.contracts.item import CreateItemInput
from planpilot.providers.github.mapper import parse_project_url, resolve_option_id
from planpilot.providers.github.models import ResolvedField

if TYPE_CHECKING:
    from planpilot.providers.github.provider import GitHubProvider

_LOG = logging.getLogger(__name__)


def resolve_create_type_policy(provider: GitHubProvider, owner_type: str) -> tuple[str, dict[str, str]]:
    strategy = provider._field_config.create_type_strategy
    if owner_type == "user" and strategy == "issue-type":
        strategy = "label"
    return strategy, dict(provider._field_config.create_type_map)


async def resolve_project_context(provider: GitHubProvider) -> tuple[str, str, int, str | None]:  # pragma: no cover
    client = provider._require_client()
    owner_type, owner, number = parse_project_url(provider._board_url)

    project_id: str | None = None
    if owner_type == "org":
        org_data = await client.fetch_org_project(owner=owner, number=number)
        org = org_data.organization
        if org and org.project_v_2:
            project_id = org.project_v_2.id
    else:
        user_data = await client.fetch_user_project(owner=owner, number=number)
        user = user_data.user
        if user and user.project_v_2:
            project_id = user.project_v_2.id

    return owner_type, owner, number, project_id


async def resolve_project_fields(  # pragma: no cover
    provider: GitHubProvider,
    project_id: str,
) -> tuple[str | None, list[dict[str, str]], ResolvedField | None, ResolvedField | None, ResolvedField | None]:
    from planpilot.providers.github.github_gql.fetch_project_fields import (
        FetchProjectFieldsNodeProjectV2,
        FetchProjectFieldsNodeProjectV2FieldsNodesProjectV2IterationField,
        FetchProjectFieldsNodeProjectV2FieldsNodesProjectV2SingleSelectField,
    )

    client = provider._require_client()
    data = await client.fetch_project_fields(project_id=project_id)

    if not isinstance(data.node, FetchProjectFieldsNodeProjectV2):
        _LOG.warning("Could not resolve project fields for %s", project_id)
        return None, [], None, None, None

    size_field_id: str | None = None
    size_options: list[dict[str, str]] = []
    status_field: ResolvedField | None = None
    priority_field: ResolvedField | None = None
    iteration_field: ResolvedField | None = None
    size_field_name = provider._field_config.size_field

    for node in data.node.fields.nodes or []:
        if node is None:
            continue
        name = node.name

        if isinstance(node, FetchProjectFieldsNodeProjectV2FieldsNodesProjectV2SingleSelectField):
            options = [{"id": o.id, "name": o.name} for o in node.options]
            if name == size_field_name:
                size_field_id = node.id
                size_options = options
            elif name == "Status":
                status_field = ResolvedField(id=node.id, name=name, kind="single_select", options=options)
            elif name == "Priority":
                priority_field = ResolvedField(id=node.id, name=name, kind="single_select", options=options)
        elif isinstance(node, FetchProjectFieldsNodeProjectV2FieldsNodesProjectV2IterationField):
            if name == "Iteration":
                iters = [{"id": i.id, "name": i.title} for i in node.configuration.iterations]
                iteration_field = ResolvedField(id=node.id, name=name, kind="iteration", options=iters)

    return size_field_id, size_options, status_field, priority_field, iteration_field


async def ensure_project_item(provider: GitHubProvider, issue_id: str) -> str:  # pragma: no cover
    if provider.context.project_id is None:
        return ""

    async with provider._project_item_lock:
        existing = provider.context.project_item_ids.get(issue_id)
        if existing:
            return existing

        client = provider._require_client()
        data = await client.add_project_item(project_id=provider.context.project_id, content_id=issue_id)
        if data.add_project_v_2_item_by_id is None or data.add_project_v_2_item_by_id.item is None:
            raise ProviderError("addProjectV2ItemById returned no item")
        item_id = data.add_project_v_2_item_by_id.item.id
        provider.context.project_item_ids[issue_id] = item_id
        return item_id


async def ensure_project_fields(
    provider: GitHubProvider,
    project_item_id: str,
    input: CreateItemInput,
) -> None:  # pragma: no cover
    if (
        not project_item_id
        or provider.context.project_id is None
        or not input.size
        or not provider.context.size_field_id
    ):
        return

    option_id = resolve_option_id(provider.context.size_options, input.size)
    if option_id is None:
        return

    client = provider._require_client()
    await client.update_project_field(
        project_id=provider.context.project_id,
        item_id=project_item_id,
        field_id=provider.context.size_field_id,
        option_id=option_id,
    )
