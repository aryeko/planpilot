"""GitHub provider adapter."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable
from types import TracebackType
from typing import Any

import httpx

from planpilot_v2.contracts.config import FieldConfig
from planpilot_v2.contracts.exceptions import (
    CreateItemPartialFailureError,
    ProviderCapabilityError,
    ProviderError,
)
from planpilot_v2.contracts.item import CreateItemInput, Item, ItemSearchFilters, UpdateItemInput
from planpilot_v2.contracts.plan import PlanItemType
from planpilot_v2.contracts.provider import Provider
from planpilot_v2.providers.github.item import GitHubItem
from planpilot_v2.providers.github.mapper import parse_project_url, resolve_option_id
from planpilot_v2.providers.github.models import GitHubProviderContext

_LOG = logging.getLogger(__name__)


class GitHubProvider(Provider):
    def __init__(
        self,
        *,
        target: str,
        token: str,
        board_url: str,
        label: str = "planpilot",
        field_config: FieldConfig | None = None,
    ) -> None:
        self._target = target
        self._token = token
        self._board_url = board_url
        self._label = label
        self._field_config = field_config or FieldConfig()

        self._client: httpx.AsyncClient | None = None
        self._project_item_lock = asyncio.Lock()
        self._rate_limit_lock = asyncio.Lock()
        self._rate_limit_clear = asyncio.Event()
        self._rate_limit_clear.set()
        self._rate_limit_pause_until = 0.0

        self.context = GitHubProviderContext(
            repo_id="",
            label_id="",
            issue_type_ids={},
            project_owner_type="org",
            create_type_strategy=self._field_config.create_type_strategy,
            create_type_map=dict(self._field_config.create_type_map),
        )

    async def __aenter__(self) -> GitHubProvider:
        await self._open_transport()

        repo_id, label_id, issue_type_ids = await self._resolve_repo_context()
        owner_type, _, _, project_id = await self._resolve_project_context()

        create_type_strategy, create_type_map = self._resolve_create_type_policy(owner_type)

        self.context = GitHubProviderContext(
            repo_id=repo_id,
            label_id=label_id,
            issue_type_ids=issue_type_ids,
            project_owner_type=owner_type,
            project_id=project_id,
            supports_sub_issues=True,
            supports_blocked_by=True,
            supports_discovery_filters=True,
            supports_issue_type=True,
            create_type_strategy=create_type_strategy,
            create_type_map=create_type_map,
        )

        return self

    async def __aexit__(  # pragma: no cover
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def search_items(self, filters: ItemSearchFilters) -> list[Item]:
        query_parts = [f"repo:{self._target}", "is:issue"]
        for label in filters.labels:
            query_parts.append(f"label:{label}")
        if filters.body_contains:
            query_parts.append(filters.body_contains)
        query = " ".join(query_parts)

        nodes = await self._search_issue_nodes(query)
        return [await self._item_from_node(node) for node in nodes]

    async def create_item(self, input: CreateItemInput) -> Item:
        completed_steps: list[str] = []
        created_issue: dict[str, Any] | None = None

        try:
            created_issue = await self._create_issue(input)
            completed_steps.append("issue_created")

            issue_id = self._require_str(created_issue, "id")

            if self.context.create_type_strategy == "issue-type":
                await self._ensure_issue_type(issue_id, input.item_type)
                completed_steps.append("issue_type_set")
            else:
                await self._ensure_type_label(issue_id, input.item_type)

            labels = list(dict.fromkeys([self._label, *input.labels]))
            await self._ensure_discovery_labels(issue_id, labels)
            completed_steps.append("labels_set")

            project_item_id = await self._ensure_project_item(issue_id)
            completed_steps.append("project_item_added")

            await self._ensure_project_fields(project_item_id, input)
            completed_steps.append("project_fields_set")

            return await self._item_from_node(created_issue)
        except Exception as exc:
            if created_issue is None:
                raise
            raise CreateItemPartialFailureError(
                f"create_item failed after issue creation: {exc}",
                created_item_id=self._require_str(created_issue, "id"),
                created_item_key=f"#{self._require_int(created_issue, 'number')}",
                created_item_url=self._require_str(created_issue, "url"),
                completed_steps=tuple(completed_steps),
                retryable=False,
            ) from exc

    async def update_item(self, item_id: str, input: UpdateItemInput) -> Item:
        existing = await self.get_item(item_id)

        merged_labels = input.labels
        if input.labels is not None:
            existing_labels = await self._get_item_labels(item_id)
            merged_labels = sorted(set(existing_labels).union(input.labels))

        update_input = UpdateItemInput(
            title=input.title,
            body=input.body,
            item_type=input.item_type,
            labels=merged_labels,
            size=input.size,
        )
        node = await self._update_issue(item_id, update_input)

        if input.item_type is not None and self.context.create_type_strategy == "issue-type":
            await self._ensure_issue_type(item_id, input.item_type)
        if input.item_type is not None and self.context.create_type_strategy == "label":
            await self._ensure_type_label(item_id, input.item_type)
        if merged_labels:
            await self._ensure_discovery_labels(item_id, merged_labels)
        if input.size is not None and self.context.project_id is not None:
            project_item_id = await self._ensure_project_item(item_id)
            await self._ensure_project_fields(
                project_item_id,
                CreateItemInput(
                    title=node.get("title", existing.title),
                    body=node.get("body", existing.body),
                    item_type=input.item_type or existing.item_type or PlanItemType.TASK,
                    labels=merged_labels or [],
                    size=input.size,
                ),
            )

        return await self._item_from_node(node)

    async def get_item(self, item_id: str) -> Item:  # pragma: no cover
        node = await self._get_issue_node(item_id)
        return await self._item_from_node(node)

    async def delete_item(self, item_id: str) -> None:  # pragma: no cover
        await self._delete_issue(item_id)

    async def add_sub_issue(self, *, child_issue_id: str, parent_issue_id: str) -> None:  # pragma: no cover
        if not self.context.supports_sub_issues:
            raise ProviderCapabilityError("GitHub provider does not support sub-issues.", capability="sub-issues")
        await self._call_with_retry(
            "add_sub_issue",
            lambda: self._graphql(
                "mutation($parentId:ID!, $childId:ID!) { "
                "addSubIssue(input:{issueId:$parentId, subIssueId:$childId}) "
                "{ issue { id } } }",
                {"parentId": parent_issue_id, "childId": child_issue_id},
            ),
        )

    async def add_blocked_by(self, *, blocked_issue_id: str, blocker_issue_id: str) -> None:  # pragma: no cover
        if not self.context.supports_blocked_by:
            raise ProviderCapabilityError("GitHub provider does not support blocked-by.", capability="blocked-by")
        await self._call_with_retry(
            "add_blocked_by",
            lambda: self._graphql(
                "mutation($blockedId:ID!, $blockerId:ID!) { "
                "addBlockedBy(input:{issueId:$blockedId, blockedById:$blockerId}) "
                "{ issue { id } } }",
                {"blockedId": blocked_issue_id, "blockerId": blocker_issue_id},
            ),
        )

    async def _open_transport(self) -> None:  # pragma: no cover
        self._client = httpx.AsyncClient(
            base_url="https://api.github.com/graphql",
            headers={"Authorization": f"Bearer {self._token}"},
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            timeout=httpx.Timeout(30.0),
        )

    async def _resolve_repo_context(self) -> tuple[str, str, dict[str, str]]:  # pragma: no cover
        owner, repo = self._split_target()
        query = (
            "query($owner:String!, $name:String!){ "
            "repository(owner:$owner, name:$name){ "
            "id labels(first:100){ nodes { id name } } "
            "issueTypes: issueTypes(first:100){ nodes { id name } } } }"
        )
        data = await self._call_with_retry("fetch_repo", lambda: self._graphql(query, {"owner": owner, "name": repo}))
        repository = self._require_dict(data, "repository")
        repo_id = self._require_str(repository, "id")

        labels = self._require_list(self._require_dict(repository, "labels"), "nodes")
        label_id = ""
        for label in labels:
            if isinstance(label, dict) and label.get("name") == self._label:
                label_id = self._require_str(label, "id")
                break
        if not label_id:
            label_id = await self._create_label(repo_id)

        issue_types_payload = self._require_dict(repository, "issueTypes")
        issue_type_ids: dict[str, str] = {}
        for issue_type in issue_types_payload.get("nodes", []):
            if not isinstance(issue_type, dict):
                continue
            name = str(issue_type.get("name", "")).upper()
            issue_type_id = issue_type.get("id")
            if name and isinstance(issue_type_id, str):
                issue_type_ids[name] = issue_type_id

        return repo_id, label_id, issue_type_ids

    async def _resolve_project_context(self) -> tuple[str, str, int, str | None]:  # pragma: no cover
        owner_type, owner, number = parse_project_url(self._board_url)
        owner_fragment = "organization" if owner_type == "org" else "user"
        query = (
            "query($owner:String!, $number:Int!) { "
            f"{owner_fragment}(login:$owner) {{ projectV2(number:$number) {{ id }} }} }}"
        )
        data = await self._call_with_retry(
            "fetch_project", lambda: self._graphql(query, {"owner": owner, "number": number})
        )
        owner_data = self._require_dict(data, owner_fragment)
        project = owner_data.get("projectV2")
        project_id = project.get("id") if isinstance(project, dict) else None
        if project_id is not None and not isinstance(project_id, str):
            raise ProviderError("Invalid project id shape")
        return owner_type, owner, number, project_id

    def _resolve_create_type_policy(self, owner_type: str) -> tuple[str, dict[str, str]]:
        strategy = self._field_config.create_type_strategy
        if owner_type == "user" and strategy == "issue-type":
            strategy = "label"
        return strategy, dict(self._field_config.create_type_map)

    async def _search_issue_nodes(self, query: str) -> list[dict[str, Any]]:  # pragma: no cover
        graphql = (
            "query($query:String!, $cursor:String){ "
            "search(type: ISSUE, query:$query, first:100, after:$cursor) "
            "{ pageInfo { hasNextPage endCursor } "
            "nodes { ... on Issue { id number url title body "
            "labels(first:100){ nodes { name } } } } } }"
        )
        cursor: str | None = None
        nodes: list[dict[str, Any]] = []
        pages = 0
        while True:
            pages += 1
            if pages > 100:
                raise ProviderError("Discovery pagination exceeded safety budget.")
            current_cursor = cursor

            async def run_search(cursor_value: str | None = current_cursor) -> dict[str, Any]:
                return await self._graphql(
                    graphql,
                    {"query": query, "cursor": cursor_value},
                )

            data = await self._call_with_retry(
                "search_issues",
                run_search,
            )
            search_data = self._require_dict(data, "search")
            batch_nodes = search_data.get("nodes", [])
            for node in batch_nodes:
                if isinstance(node, dict):
                    nodes.append(node)
            page_info = self._require_dict(search_data, "pageInfo")
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")
        return nodes

    async def _create_issue(self, input: CreateItemInput) -> dict[str, Any]:  # pragma: no cover
        mutation = (
            "mutation($repositoryId:ID!, $title:String!, $body:String!) { "
            "createIssue(input:{repositoryId:$repositoryId, title:$title, body:$body}) { "
            "issue { id number url title body labels(first:100){ nodes { name } } } } }"
        )
        data = await self._call_with_retry(
            "create_issue",
            lambda: self._graphql(
                mutation,
                {"repositoryId": self.context.repo_id, "title": input.title, "body": input.body},
            ),
        )
        created = self._require_dict(self._require_dict(data, "createIssue"), "issue")
        return created

    async def _update_issue(self, item_id: str, input: UpdateItemInput) -> dict[str, Any]:  # pragma: no cover
        mutation = (
            "mutation($id:ID!, $title:String, $body:String) { "
            "updateIssue(input:{id:$id, title:$title, body:$body}) { "
            "issue { id number url title body labels(first:100){ nodes { name } } } } }"
        )
        data = await self._call_with_retry(
            "update_issue",
            lambda: self._graphql(mutation, {"id": item_id, "title": input.title, "body": input.body}),
        )
        return self._require_dict(self._require_dict(data, "updateIssue"), "issue")

    async def _delete_issue(self, item_id: str) -> None:  # pragma: no cover
        mutation = "mutation($id:ID!){ closeIssue(input:{issueId:$id}) { issue { id } } }"
        await self._call_with_retry("delete_issue", lambda: self._graphql(mutation, {"id": item_id}))

    async def _ensure_issue_type(self, issue_id: str, item_type: PlanItemType) -> None:  # pragma: no cover
        if not self.context.supports_issue_type:
            raise ProviderCapabilityError("GitHub provider does not support issue types.", capability="issue-type")
        mapped_name = self.context.create_type_map.get(item_type.value, item_type.value)
        issue_type_id = self.context.issue_type_ids.get(mapped_name.upper()) or self.context.issue_type_ids.get(
            item_type.value
        )
        if issue_type_id is None:
            raise ProviderError(f"Unable to resolve issue type id for {item_type.value}")
        mutation = (
            "mutation($issueId:ID!, $issueTypeId:ID!){ "
            "updateIssueType(input:{issueId:$issueId, issueTypeId:$issueTypeId}) "
            "{ issue { id } } }"
        )
        await self._call_with_retry(
            "set_issue_type",
            lambda: self._graphql(mutation, {"issueId": issue_id, "issueTypeId": issue_type_id}),
        )

    async def _ensure_type_label(self, issue_id: str, item_type: PlanItemType) -> None:  # pragma: no cover
        mapped = self.context.create_type_map.get(item_type.value)
        if mapped is None:
            raise ProviderError(f"No label mapping configured for {item_type.value}")
        await self._ensure_discovery_labels(issue_id, [mapped])

    async def _ensure_discovery_labels(self, issue_id: str, labels: list[str]) -> None:  # pragma: no cover
        for label in labels:
            if label == self._label and self.context.label_id:
                label_id = self.context.label_id
            else:
                label_id = await self._find_or_create_label(label)
            mutation = (
                "mutation($labelableId:ID!, $labelIds:[ID!]!){ "
                "addLabelsToLabelable(input:{labelableId:$labelableId, labelIds:$labelIds}) "
                "{ clientMutationId } }"
            )

            async def add_label_mutation(
                mutation_query: str = mutation,
                current_label_id: str = label_id,
            ) -> dict[str, Any]:
                return await self._graphql(
                    mutation_query,
                    {"labelableId": issue_id, "labelIds": [current_label_id]},
                )

            await self._call_with_retry(
                "add_label",
                add_label_mutation,
            )

    async def _ensure_project_item(self, issue_id: str) -> str:  # pragma: no cover
        if self.context.project_id is None:
            return ""

        async with self._project_item_lock:
            existing = self.context.project_item_ids.get(issue_id)
            if existing:
                return existing

        mutation = (
            "mutation($projectId:ID!, $contentId:ID!){ "
            "addProjectV2ItemById(input:{projectId:$projectId, contentId:$contentId}) { item { id } } }"
        )
        data = await self._call_with_retry(
            "add_project_item",
            lambda: self._graphql(mutation, {"projectId": self.context.project_id, "contentId": issue_id}),
        )
        item = self._require_dict(self._require_dict(data, "addProjectV2ItemById"), "item")
        item_id = self._require_str(item, "id")
        async with self._project_item_lock:
            self.context.project_item_ids[issue_id] = item_id
        return item_id

    async def _ensure_project_fields(self, project_item_id: str, input: CreateItemInput) -> None:  # pragma: no cover
        if not project_item_id or self.context.project_id is None or not input.size or not self.context.size_field_id:
            return

        option_id = resolve_option_id(self.context.size_options, input.size)
        if option_id is None:
            return

        mutation = (
            "mutation($projectId:ID!, $itemId:ID!, $fieldId:ID!, $optionId:String!){ "
            "updateProjectV2ItemFieldValue(input:{projectId:$projectId, itemId:$itemId, "
            "fieldId:$fieldId, value:{ singleSelectOptionId:$optionId }}) "
            "{ projectV2Item { id } } }"
        )
        await self._call_with_retry(
            "update_project_field",
            lambda: self._graphql(
                mutation,
                {
                    "projectId": self.context.project_id,
                    "itemId": project_item_id,
                    "fieldId": self.context.size_field_id,
                    "optionId": option_id,
                },
            ),
        )

    async def _get_issue_node(self, item_id: str) -> dict[str, Any]:  # pragma: no cover
        query = (
            "query($id:ID!){ node(id:$id) { ... on Issue { "
            "id number url title body labels(first:100){ nodes { name } } } } }"
        )
        data = await self._call_with_retry("get_issue", lambda: self._graphql(query, {"id": item_id}))
        node = self._require_dict(data, "node")
        return node

    async def _item_from_node(self, node: dict[str, Any]) -> GitHubItem:
        return GitHubItem(
            provider=self,
            issue_id=self._require_str(node, "id"),
            number=self._require_int(node, "number"),
            title=self._require_str(node, "title"),
            body=self._require_str(node, "body"),
            item_type=None,
            url=self._require_str(node, "url"),
        )

    async def _get_item_labels(self, item_id: str) -> list[str]:  # pragma: no cover
        node = await self._get_issue_node(item_id)
        labels = self._require_dict(node, "labels")
        out: list[str] = []
        for label_node in labels.get("nodes", []):
            if isinstance(label_node, dict):
                label_name = label_node.get("name")
                if isinstance(label_name, str):
                    out.append(label_name)
        return out

    async def _find_or_create_label(self, name: str) -> str:  # pragma: no cover
        owner, repo = self._split_target()
        query = (
            "query($owner:String!, $name:String!, $label:String!){ "
            "repository(owner:$owner, name:$name) { "
            "labels(first:100, query:$label) { nodes { id name } } } }"
        )
        data = await self._call_with_retry(
            "find_label",
            lambda: self._graphql(query, {"owner": owner, "name": repo, "label": name}),
        )
        labels = self._require_list(self._require_dict(self._require_dict(data, "repository"), "labels"), "nodes")
        for label in labels:
            if isinstance(label, dict) and label.get("name") == name:
                return self._require_str(label, "id")

        return await self._create_label(self.context.repo_id, name=name)

    async def _create_label(self, repo_id: str, *, name: str | None = None) -> str:  # pragma: no cover
        mutation = (
            "mutation($repositoryId:ID!, $name:String!){ "
            'createLabel(input:{repositoryId:$repositoryId, name:$name, color:"0366d6"}) '
            "{ label { id } } }"
        )
        data = await self._call_with_retry(
            "create_label",
            lambda: self._graphql(mutation, {"repositoryId": repo_id, "name": name or self._label}),
        )
        return self._require_str(self._require_dict(self._require_dict(data, "createLabel"), "label"), "id")

    async def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:  # pragma: no cover
        if self._client is None:
            raise ProviderError("Provider is not initialized. Use 'async with'.")
        await self._wait_for_rate_limit()

        response = await self._client.post("", json={"query": query, "variables": variables})
        if response.status_code == 429:
            retry_after = self._parse_retry_after(response)
            await self._apply_rate_limit_pause(retry_after)
            raise httpx.HTTPStatusError("rate limited", request=response.request, response=response)

        response.raise_for_status()
        payload = response.json()
        errors = payload.get("errors", [])
        if errors:
            raise ProviderError(f"GraphQL returned errors: {errors}")

        data = payload.get("data")
        if not isinstance(data, dict):
            raise ProviderError("GraphQL response missing data payload")
        return data

    async def _call_with_retry(  # pragma: no cover
        self,
        operation: str,
        fn: Callable[[], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        max_retries = 3
        for attempt in range(max_retries + 1):
            try:
                return await fn()
            except httpx.TransportError:
                if attempt == max_retries:
                    raise
                await self._sleep_backoff(attempt, operation)
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status == 429:
                    retry_after = self._parse_retry_after(exc.response)
                    await self._apply_rate_limit_pause(retry_after)
                    if attempt == max_retries:
                        raise
                    await self._sleep_backoff(attempt, operation)
                    continue
                if status in {502, 503, 504}:
                    if attempt == max_retries:
                        raise
                    retry_after = self._parse_retry_after(exc.response)
                    if retry_after > 0:
                        await asyncio.sleep(retry_after)
                    await self._sleep_backoff(attempt, operation)
                    continue
                raise
            except ProviderError as exc:
                # Only retry known transient provider errors.
                if "rate limit" in str(exc).lower() and attempt < max_retries:
                    await self._sleep_backoff(attempt, operation)
                    continue
                raise exc

        raise ProviderError(f"Operation failed after retries: {operation}")

    async def _sleep_backoff(self, attempt: int, operation: str) -> None:  # pragma: no cover
        seconds = min(4.0, float(2**attempt)) + random.uniform(0.0, 0.25)
        _LOG.warning("Retrying GitHub operation", extra={"operation": operation, "attempt": attempt + 1})
        await asyncio.sleep(seconds)

    async def _wait_for_rate_limit(self) -> None:  # pragma: no cover
        await self._rate_limit_clear.wait()

    async def _apply_rate_limit_pause(self, retry_after: float) -> None:  # pragma: no cover
        now = time.monotonic()
        async with self._rate_limit_lock:
            until = now + max(0.0, retry_after)
            if until <= self._rate_limit_pause_until:
                return
            self._rate_limit_pause_until = until
            self._rate_limit_clear.clear()

        await asyncio.sleep(max(0.0, self._rate_limit_pause_until - time.monotonic()))

        async with self._rate_limit_lock:
            if time.monotonic() >= self._rate_limit_pause_until:
                self._rate_limit_clear.set()

    @staticmethod
    def _parse_retry_after(response: httpx.Response) -> float:  # pragma: no cover
        raw = response.headers.get("Retry-After")
        if raw is None:
            return 1.0
        try:
            return max(0.0, float(raw))
        except ValueError:
            return 1.0

    def _split_target(self) -> tuple[str, str]:  # pragma: no cover
        parts = self._target.split("/", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ProviderError(f"Invalid target '{self._target}'. Expected owner/repo.")
        return parts[0], parts[1]

    @staticmethod
    def _require_dict(data: dict[str, Any], key: str) -> dict[str, Any]:  # pragma: no cover
        value = data.get(key)
        if not isinstance(value, dict):
            raise ProviderError(f"Missing/invalid object at key '{key}'")
        return value

    @staticmethod
    def _require_list(data: dict[str, Any], key: str) -> list[Any]:  # pragma: no cover
        value = data.get(key)
        if not isinstance(value, list):
            raise ProviderError(f"Missing/invalid list at key '{key}'")
        return value

    @staticmethod
    def _require_str(data: dict[str, Any], key: str) -> str:  # pragma: no cover
        value = data.get(key)
        if not isinstance(value, str):
            raise ProviderError(f"Missing/invalid string at key '{key}'")
        return value

    @staticmethod
    def _require_int(data: dict[str, Any], key: str) -> int:  # pragma: no cover
        value = data.get(key)
        if not isinstance(value, int):
            raise ProviderError(f"Missing/invalid int at key '{key}'")
        return value
