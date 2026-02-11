"""GitHub provider adapter - uses the ariadne-codegen generated GraphQL client."""

from __future__ import annotations

import asyncio
import logging
from types import TracebackType

import httpx

from planpilot.contracts.config import FieldConfig
from planpilot.contracts.exceptions import (
    CreateItemPartialFailureError,
    ProviderCapabilityError,
    ProviderError,
)
from planpilot.contracts.item import CreateItemInput, Item, ItemSearchFilters, UpdateItemInput
from planpilot.contracts.plan import PlanItemType
from planpilot.contracts.provider import Provider
from planpilot.providers.github.github_gql.client import GitHubGraphQLClient
from planpilot.providers.github.github_gql.exceptions import GraphQLClientError
from planpilot.providers.github.github_gql.fragments import IssueCore
from planpilot.providers.github.github_gql.search_issues import SearchIssuesSearchNodesIssue
from planpilot.providers.github.item import GitHubItem
from planpilot.providers.github.mapper import parse_project_url, resolve_option_id
from planpilot.providers.github.models import GitHubProviderContext, ResolvedField

_LOG = logging.getLogger(__name__)


class GitHubProvider(Provider):
    """Thin adapter that delegates all GitHub GraphQL interactions to the generated client."""

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

        self._client: GitHubGraphQLClient | None = None
        self._project_item_lock = asyncio.Lock()

        self.context = GitHubProviderContext(
            repo_id="",
            label_id="",
            issue_type_ids={},
            project_owner_type="org",
            create_type_strategy=self._field_config.create_type_strategy,
            create_type_map=dict(self._field_config.create_type_map),
        )

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> GitHubProvider:
        await self._open_transport()

        repo_id, label_id, issue_type_ids = await self._resolve_repo_context()
        owner_type, _, _, project_id = await self._resolve_project_context()

        # Resolve project field metadata (Size, Status, Priority, Iteration)
        size_field_id: str | None = None
        size_options: list[dict[str, str]] = []
        status_field: ResolvedField | None = None
        priority_field: ResolvedField | None = None
        iteration_field: ResolvedField | None = None
        if project_id:
            (
                size_field_id,
                size_options,
                status_field,
                priority_field,
                iteration_field,
            ) = await self._resolve_project_fields(project_id)

        create_type_strategy, create_type_map = self._resolve_create_type_policy(owner_type)

        # Detect issue-type capability from repo metadata
        has_issue_types = bool(issue_type_ids)
        if create_type_strategy == "issue-type" and not has_issue_types:
            _LOG.warning(
                "create_type_strategy is 'issue-type' but repository has no issue types configured; "
                "falling back to 'label' strategy"
            )
            create_type_strategy = "label"

        self.context = GitHubProviderContext(
            repo_id=repo_id,
            label_id=label_id,
            issue_type_ids=issue_type_ids,
            project_owner_type=owner_type,
            project_id=project_id,
            size_field_id=size_field_id,
            size_options=size_options,
            status_field=status_field,
            priority_field=priority_field,
            iteration_field=iteration_field,
            supports_sub_issues=True,
            supports_blocked_by=True,
            supports_discovery_filters=True,
            supports_issue_type=has_issue_types,
            create_type_strategy=create_type_strategy,
            create_type_map=create_type_map,
        )

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._client is not None:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            self._client = None

    # ------------------------------------------------------------------
    # Provider contract
    # ------------------------------------------------------------------

    async def search_items(self, filters: ItemSearchFilters) -> list[Item]:
        query_parts = [f"repo:{self._target}", "is:issue"]
        for label in filters.labels:
            query_parts.append(f"label:{label}")
        if filters.body_contains:
            query_parts.append(f'"{filters.body_contains}" in:body')
        query = " ".join(query_parts)

        nodes = await self._search_issue_nodes(query)
        return [self._item_from_issue_core(node) for node in nodes]

    async def create_item(self, input: CreateItemInput) -> Item:
        completed_steps: list[str] = []
        issue: IssueCore | None = None

        try:
            # _create_issue atomically sets labels, issue type, and project
            issue = await self._create_issue(input)
            completed_steps.extend(["issue_created", "issue_type_set", "labels_set"])

            # Only project field assignment (e.g. Size) requires follow-up calls
            if self.context.project_id:
                project_item_id = await self._ensure_project_item(issue.id)
                completed_steps.append("project_item_added")

                await self._ensure_project_fields(project_item_id, input)
                completed_steps.append("project_fields_set")

            return self._item_from_issue_core(issue)
        except Exception as exc:
            if issue is None:
                raise
            raise CreateItemPartialFailureError(
                f"create_item failed after issue creation: {exc}",
                created_item_id=issue.id,
                created_item_key=f"#{issue.number}",
                created_item_url=issue.url,
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
        issue = await self._update_issue(item_id, update_input)

        # issue_type_id is already set atomically in _update_issue for "issue-type" strategy
        if input.item_type is not None and self.context.create_type_strategy == "label":
            await self._ensure_type_label(item_id, input.item_type)
        if merged_labels:
            await self._ensure_discovery_labels(item_id, merged_labels)
        if input.size is not None and self.context.project_id is not None:
            project_item_id = await self._ensure_project_item(item_id)
            await self._ensure_project_fields(
                project_item_id,
                CreateItemInput(
                    title=issue.title,
                    body=issue.body,
                    item_type=input.item_type or existing.item_type or PlanItemType.TASK,
                    labels=merged_labels or [],
                    size=input.size,
                ),
            )

        return self._item_from_issue_core(issue)

    async def get_item(self, item_id: str) -> Item:  # pragma: no cover
        issue = await self._get_issue(item_id)
        return self._item_from_issue_core(issue)

    async def delete_item(self, item_id: str) -> None:  # pragma: no cover
        client = self._require_client()
        await client.delete_issue(issue_id=item_id)

    async def add_sub_issue(self, *, child_issue_id: str, parent_issue_id: str) -> None:  # pragma: no cover
        if not self.context.supports_sub_issues:
            raise ProviderCapabilityError("GitHub provider does not support sub-issues.", capability="sub-issues")
        client = self._require_client()
        try:
            await client.add_sub_issue(parent_id=parent_issue_id, child_id=child_issue_id)
        except GraphQLClientError as exc:
            if self._is_duplicate_relation_error(exc):
                _LOG.debug("Sub-issue relationship already exists: %s -> %s", child_issue_id, parent_issue_id)
                return
            raise ProviderError(f"Failed to add sub-issue: {exc}") from exc

    async def add_blocked_by(self, *, blocked_issue_id: str, blocker_issue_id: str) -> None:  # pragma: no cover
        if not self.context.supports_blocked_by:
            raise ProviderCapabilityError("GitHub provider does not support blocked-by.", capability="blocked-by")
        client = self._require_client()
        try:
            await client.add_blocked_by(blocked_id=blocked_issue_id, blocker_id=blocker_issue_id)
        except GraphQLClientError as exc:
            if self._is_duplicate_relation_error(exc):
                _LOG.debug("Blocked-by relationship already exists: %s -> %s", blocked_issue_id, blocker_issue_id)
                return
            raise ProviderError(f"Failed to add blocked-by relation: {exc}") from exc

    # ------------------------------------------------------------------
    # Relation error helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_duplicate_relation_error(exc: GraphQLClientError) -> bool:
        """Check if a GraphQL error indicates a relation that already exists."""
        msg = str(exc).lower()
        return (
            "duplicate sub-issues" in msg
            or "may only have one parent" in msg
            or "already exists" in msg
            or "has already been taken" in msg
        )

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    async def _open_transport(self) -> None:  # pragma: no cover
        from planpilot.providers.github._retrying_transport import RetryingTransport

        transport = RetryingTransport()
        http = httpx.AsyncClient(
            transport=transport,
            headers={"Authorization": f"Bearer {self._token}"},
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            timeout=httpx.Timeout(30.0),
        )
        self._client = GitHubGraphQLClient(
            url="https://api.github.com/graphql",
            http_client=http,
        )

    def _require_client(self) -> GitHubGraphQLClient:
        if self._client is None:
            raise ProviderError("Provider is not initialized. Use 'async with'.")
        return self._client

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    async def _resolve_repo_context(self) -> tuple[str, str, dict[str, str]]:  # pragma: no cover
        client = self._require_client()
        owner, repo = self._split_target()
        data = await client.fetch_repo(owner=owner, name=repo)

        repository = data.repository
        if repository is None:
            raise ProviderError("Repository not found")
        repo_id = repository.id

        # Resolve label
        label_id = ""
        if repository.labels and repository.labels.nodes:
            for node in repository.labels.nodes:
                if node and node.name == self._label:
                    label_id = node.id
                    break
        if not label_id:
            label_id = await self._create_label(repo_id)

        # Resolve issue types
        issue_type_ids: dict[str, str] = {}
        if repository.issue_types and repository.issue_types.nodes:
            for it_node in repository.issue_types.nodes:
                if it_node:
                    issue_type_ids[it_node.name.upper()] = it_node.id

        return repo_id, label_id, issue_type_ids

    async def _resolve_project_context(self) -> tuple[str, str, int, str | None]:  # pragma: no cover
        client = self._require_client()
        owner_type, owner, number = parse_project_url(self._board_url)

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

    def _resolve_create_type_policy(self, owner_type: str) -> tuple[str, dict[str, str]]:
        strategy = self._field_config.create_type_strategy
        if owner_type == "user" and strategy == "issue-type":
            strategy = "label"
        return strategy, dict(self._field_config.create_type_map)

    async def _resolve_project_fields(  # pragma: no cover
        self, project_id: str
    ) -> tuple[str | None, list[dict[str, str]], ResolvedField | None, ResolvedField | None, ResolvedField | None]:
        """Fetch project fields and resolve Size, Status, Priority, Iteration metadata."""
        from planpilot.providers.github.github_gql.fetch_project_fields import (
            FetchProjectFieldsNodeProjectV2,
            FetchProjectFieldsNodeProjectV2FieldsNodesProjectV2IterationField,
            FetchProjectFieldsNodeProjectV2FieldsNodesProjectV2SingleSelectField,
        )

        client = self._require_client()
        data = await client.fetch_project_fields(project_id=project_id)

        if not isinstance(data.node, FetchProjectFieldsNodeProjectV2):
            _LOG.warning("Could not resolve project fields for %s", project_id)
            return None, [], None, None, None

        size_field_id: str | None = None
        size_options: list[dict[str, str]] = []
        status_field: ResolvedField | None = None
        priority_field: ResolvedField | None = None
        iteration_field: ResolvedField | None = None
        size_field_name = self._field_config.size_field

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

    # ------------------------------------------------------------------
    # Issue CRUD (via generated client)
    # ------------------------------------------------------------------

    async def _search_issue_nodes(self, query: str) -> list[IssueCore]:  # pragma: no cover
        client = self._require_client()
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

    async def _create_issue(self, input: CreateItemInput) -> IssueCore:  # pragma: no cover
        client = self._require_client()

        # Resolve label IDs for atomic creation (include type label for "label" strategy)
        all_labels = list(dict.fromkeys([self._label, *input.labels]))
        if self.context.create_type_strategy == "label":
            type_label = self.context.create_type_map.get(input.item_type.value)
            if type_label:
                all_labels = list(dict.fromkeys([*all_labels, type_label]))
        label_ids = await self._resolve_label_ids(all_labels)

        # Resolve issue type ID
        issue_type_id: str | None = None
        if self.context.create_type_strategy == "issue-type":
            mapped_name = self.context.create_type_map.get(input.item_type.value, input.item_type.value)
            issue_type_id = self.context.issue_type_ids.get(mapped_name.upper()) or self.context.issue_type_ids.get(
                input.item_type.value
            )
            if issue_type_id is None:
                _LOG.warning("Could not resolve issue type ID for %r; issue created without a type", mapped_name)

        # Resolve project IDs
        project_ids = [self.context.project_id] if self.context.project_id else None

        data = await client.create_issue(
            repository_id=self.context.repo_id,
            title=input.title,
            body=input.body,
            label_ids=label_ids or None,
            issue_type_id=issue_type_id,
            project_v_2_ids=project_ids,
        )

        if data.create_issue is None or data.create_issue.issue is None:
            raise ProviderError("createIssue returned no issue")
        return data.create_issue.issue

    async def _update_issue(self, item_id: str, input: UpdateItemInput) -> IssueCore:  # pragma: no cover
        client = self._require_client()

        # Resolve issue type ID for atomic update
        issue_type_id: str | None = None
        if input.item_type is not None and self.context.create_type_strategy == "issue-type":
            mapped_name = self.context.create_type_map.get(input.item_type.value, input.item_type.value)
            issue_type_id = self.context.issue_type_ids.get(mapped_name.upper()) or self.context.issue_type_ids.get(
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
        return data.update_issue.issue

    async def _get_issue(self, item_id: str) -> IssueCore:  # pragma: no cover
        client = self._require_client()
        from planpilot.providers.github.github_gql.get_issue import GetIssueNodeIssue

        data = await client.get_issue(id=item_id)
        if data.node is None or not isinstance(data.node, GetIssueNodeIssue):
            raise ProviderError(f"Issue not found: {item_id}")
        return data.node

    async def _get_item_labels(self, item_id: str) -> list[str]:  # pragma: no cover
        issue = await self._get_issue(item_id)
        if issue.labels and issue.labels.nodes:
            return [n.name for n in issue.labels.nodes if n]
        return []

    # ------------------------------------------------------------------
    # Issue type helpers
    # ------------------------------------------------------------------

    async def _ensure_issue_type(self, issue_id: str, item_type: PlanItemType) -> None:  # pragma: no cover
        """Set issue type via updateIssue mutation (correct approach)."""
        if not self.context.supports_issue_type:
            raise ProviderCapabilityError("GitHub provider does not support issue types.", capability="issue-type")
        mapped_name = self.context.create_type_map.get(item_type.value, item_type.value)
        issue_type_id = self.context.issue_type_ids.get(mapped_name.upper()) or self.context.issue_type_ids.get(
            item_type.value
        )
        if issue_type_id is None:
            raise ProviderError(f"Unable to resolve issue type id for {item_type.value}")
        client = self._require_client()
        await client.update_issue(id=issue_id, issue_type_id=issue_type_id)

    async def _ensure_type_label(self, issue_id: str, item_type: PlanItemType) -> None:  # pragma: no cover
        mapped = self.context.create_type_map.get(item_type.value)
        if mapped is None:
            raise ProviderError(f"No label mapping configured for {item_type.value}")
        await self._ensure_discovery_labels(issue_id, [mapped])

    # ------------------------------------------------------------------
    # Label helpers
    # ------------------------------------------------------------------

    async def _ensure_discovery_labels(self, issue_id: str, labels: list[str]) -> None:  # pragma: no cover
        label_ids = await self._resolve_label_ids(labels)
        if label_ids:
            client = self._require_client()
            await client.add_labels(labelable_id=issue_id, label_ids=label_ids)

    async def _resolve_label_ids(self, label_names: list[str]) -> list[str]:  # pragma: no cover
        """Resolve a list of label names to their IDs, creating if needed."""
        ids: list[str] = []
        for name in label_names:
            if name == self._label and self.context.label_id:
                ids.append(self.context.label_id)
            else:
                ids.append(await self._find_or_create_label(name))
        return ids

    async def _find_or_create_label(self, name: str) -> str:  # pragma: no cover
        client = self._require_client()
        owner, repo = self._split_target()
        data = await client.find_labels(owner=owner, name=repo, query=name)
        if data.repository and data.repository.labels and data.repository.labels.nodes:
            for node in data.repository.labels.nodes:
                if node and node.name == name:
                    return node.id
        return await self._create_label(self.context.repo_id, name=name)

    async def _create_label(self, repo_id: str, *, name: str | None = None) -> str:  # pragma: no cover
        client = self._require_client()
        data = await client.create_label(repository_id=repo_id, name=name or self._label)
        if data.create_label is None or data.create_label.label is None:
            raise ProviderError("createLabel returned no label")
        return data.create_label.label.id

    # ------------------------------------------------------------------
    # Project helpers
    # ------------------------------------------------------------------

    async def _ensure_project_item(self, issue_id: str) -> str:  # pragma: no cover
        if self.context.project_id is None:
            return ""

        async with self._project_item_lock:
            existing = self.context.project_item_ids.get(issue_id)
            if existing:
                return existing

            client = self._require_client()
            data = await client.add_project_item(project_id=self.context.project_id, content_id=issue_id)
            if data.add_project_v_2_item_by_id is None or data.add_project_v_2_item_by_id.item is None:
                raise ProviderError("addProjectV2ItemById returned no item")
            item_id = data.add_project_v_2_item_by_id.item.id
            self.context.project_item_ids[issue_id] = item_id
            return item_id

    async def _ensure_project_fields(self, project_item_id: str, input: CreateItemInput) -> None:  # pragma: no cover
        if not project_item_id or self.context.project_id is None or not input.size or not self.context.size_field_id:
            return

        option_id = resolve_option_id(self.context.size_options, input.size)
        if option_id is None:
            return

        client = self._require_client()
        await client.update_project_field(
            project_id=self.context.project_id,
            item_id=project_item_id,
            field_id=self.context.size_field_id,
            option_id=option_id,
        )

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def _item_from_issue_core(self, issue: IssueCore) -> GitHubItem:
        return GitHubItem(
            provider=self,
            issue_id=issue.id,
            number=issue.number,
            title=issue.title,
            body=issue.body,
            item_type=None,
            url=issue.url,
        )

    def _split_target(self) -> tuple[str, str]:  # pragma: no cover
        parts = self._target.split("/", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ProviderError(f"Invalid target '{self._target}'. Expected owner/repo.")
        return parts[0], parts[1]
