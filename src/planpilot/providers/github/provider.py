"""GitHub provider implementation for planpilot (refactored for new Provider ABC).

Implements the thin CRUD layer Provider ABC using gh CLI and GraphQL.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, TYPE_CHECKING

from planpilot.exceptions import ProjectURLError, ProviderError
from planpilot.models.item import CreateItemInput, ItemFields, ItemType, TargetContext, UpdateItemInput
from planpilot.models.project import FieldConfig, FieldValue, ResolvedField
from planpilot.providers.base import Provider
from planpilot.providers.github.client import GhClient
from planpilot.providers.github.item import GitHubItem
from planpilot.providers.github.mapper import (
    parse_markers,
    parse_project_url,
    resolve_option_id,
)
from planpilot.providers.github.queries import (
    ADD_BLOCKED_BY,
    ADD_PROJECT_ITEM,
    ADD_SUB_ISSUE,
    CREATE_ISSUE,
    FETCH_ISSUE_RELATIONS,
    FETCH_PROJECT,
    FETCH_PROJECT_ITEMS,
    FETCH_REPO,
    SEARCH_ISSUES,
    UPDATE_ISSUE_TYPE,
    UPDATE_PROJECT_FIELD,
)

if TYPE_CHECKING:
    from planpilot.providers.item import Item

logger = logging.getLogger(__name__)


class GitHubTargetContext(TargetContext):
    """GitHub-specific target context (opaque to the engine)."""

    repo: str
    board_url: str | None
    repo_id: str | None
    repo_label_id: str | None
    issue_type_ids: dict[str, str]
    project_id: str | None
    status_field: ResolvedField | None
    priority_field: ResolvedField | None
    iteration_field: ResolvedField | None
    size_field_id: str | None
    size_options: list[dict[str, str]]


class GitHubProvider(Provider):
    """GitHub provider implementing the Provider ABC using gh CLI and GraphQL."""

    def __init__(
        self,
        *,
        target: str,
        board_url: str | None = None,
        label: str | None = None,
        field_config: FieldConfig | None = None,
        client: GhClient | None = None,
    ) -> None:
        """Initialize the GitHub provider.

        Args:
            target: Repository in "owner/repo" format.
            board_url: GitHub Projects v2 board URL (optional).
            label: Label to apply to created items.
            field_config: Project field configuration.
            client: GitHub client (optional; created if not provided).
        """
        self.target = target
        self.board_url = board_url
        self.label = label or "planpilot"
        self.field_config = field_config or FieldConfig()
        self.client = client or GhClient()
        self._ctx: GitHubTargetContext | None = None

    # ---- Context manager lifecycle ----

    async def __aenter__(self) -> Provider:
        """Enter async context manager.

        Performs authentication, target resolution, field resolution, etc.
        """
        await self.client.check_auth()

        owner, repo = self.target.split("/", 1)

        # Fetch repo context
        response = await self.client.graphql(
            FETCH_REPO,
            variables={"owner": owner, "name": repo, "label": self.label},
        )

        repo_data = response.get("data", {}).get("repository")
        if not repo_data:
            raise ProviderError(f"Repository {self.target} not found")

        repo_id = repo_data.get("id")
        issue_types = repo_data.get("issueTypes", {}).get("nodes", [])
        labels = repo_data.get("labels", {}).get("nodes", [])

        # Build issue type map
        issue_type_ids: dict[str, str] = {}
        for it in issue_types:
            it_name = it.get("name")
            it_id = it.get("id")
            if it_name and it_id:
                issue_type_ids[it_name] = it_id

        # Check if label exists, create if not
        repo_label_id: str | None = None
        if labels:
            repo_label_id = labels[0].get("id")
        else:
            logger.info("Label '%s' not found in %s, attempting to create it", self.label, self.target)
            try:
                await self.client.run(
                    ["label", "create", self.label, "--repo", self.target],
                    check=True,
                )
                # Re-fetch to get the label ID
                response = await self.client.graphql(
                    FETCH_REPO,
                    variables={"owner": owner, "name": repo, "label": self.label},
                )
                repo_data = response.get("data", {}).get("repository", {})
                labels = repo_data.get("labels", {}).get("nodes", [])
                if labels:
                    repo_label_id = labels[0].get("id")
            except ProviderError as e:
                logger.warning("Failed to create label '%s': %s", self.label, e)
            except (OSError, TypeError, KeyError, AttributeError) as e:
                logger.warning("Unexpected error creating label '%s': %s: %s", self.label, type(e).__name__, e)

        # Fetch project context (if board_url provided)
        project_id: str | None = None
        status_field: ResolvedField | None = None
        priority_field: ResolvedField | None = None
        iteration_field: ResolvedField | None = None
        size_field_id: str | None = None
        size_options: list[dict[str, str]] = []

        if self.board_url:
            try:
                org, number = parse_project_url(self.board_url)
                response = await self.client.graphql(
                    FETCH_PROJECT,
                    variables={"org": org, "number": number},
                )
                project_data = response.get("data", {}).get("organization", {}).get("projectV2")
                if project_data:
                    project_id = project_data.get("id")
                    fields = project_data.get("fields", {}).get("nodes", [])

                    for field in fields:
                        field_id = field.get("id")
                        field_name = field.get("name", "")

                        # Status field
                        if field_name == "Status" and "options" in field:
                            options = field.get("options", [])
                            option_id = resolve_option_id(options, self.field_config.status)
                            if option_id:
                                status_field = ResolvedField(
                                    field_id=field_id,
                                    value=FieldValue(single_select_option_id=option_id),
                                )

                        # Priority field
                        if field_name == "Priority" and "options" in field:
                            options = field.get("options", [])
                            option_id = resolve_option_id(options, self.field_config.priority)
                            if option_id:
                                priority_field = ResolvedField(
                                    field_id=field_id,
                                    value=FieldValue(single_select_option_id=option_id),
                                )

                        # Iteration field
                        if field_name == "Iteration" and "configuration" in field:
                            config = field.get("configuration", {})
                            iterations = config.get("iterations", [])
                            iteration_id: str | None = None

                            if self.field_config.iteration == "active":
                                now = datetime.now(UTC)
                                for it in iterations:
                                    start = it.get("startDate")
                                    duration = it.get("duration")
                                    if not start or duration is None:
                                        continue
                                    try:
                                        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                                    except ValueError:
                                        continue
                                    if start_dt.tzinfo is None:
                                        start_dt = start_dt.replace(tzinfo=UTC)
                                    end_dt = start_dt + timedelta(days=int(duration))
                                    if start_dt <= now < end_dt:
                                        iteration_id = it.get("id")
                                        break
                            else:
                                for it in iterations:
                                    if it.get("title", "").lower() == self.field_config.iteration.lower():
                                        iteration_id = it.get("id")
                                        break

                            if iteration_id:
                                iteration_field = ResolvedField(
                                    field_id=field_id,
                                    value=FieldValue(iteration_id=iteration_id),
                                )

                        # Size field
                        if field_name == self.field_config.size_field and "options" in field:
                            size_field_id = field_id
                            size_options = [
                                {"id": opt.get("id"), "name": opt.get("name")}
                                for opt in field.get("options", [])
                                if opt.get("id") and opt.get("name")
                            ]
            except ProjectURLError:
                logger.error("Invalid board URL: %s", self.board_url)
            except Exception as e:
                logger.error("Failed to fetch project context: %s", e, exc_info=True)

        # Store context
        self._ctx = GitHubTargetContext(
            repo=self.target,
            board_url=self.board_url,
            repo_id=repo_id,
            repo_label_id=repo_label_id,
            issue_type_ids=issue_type_ids,
            project_id=project_id,
            status_field=status_field,
            priority_field=priority_field,
            iteration_field=iteration_field,
            size_field_id=size_field_id,
            size_options=size_options,
        )

        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit async context manager. Clean up resources."""
        await self.client.close()

    # ---- Search ----

    async def search_items(self, filters: ItemFields) -> list[Item]:
        """Search for work items matching filters.

        Currently supports filtering by labels.

        Args:
            filters: Search filters (labels field is used)

        Returns:
            List of GitHubItem instances
        """
        if not self._ctx:
            raise ProviderError("Provider not initialized (not in async context)")

        items: list[Item] = []

        # Build search query
        label_filter = ""
        if filters.labels:
            for label in filters.labels:
                label_filter += f' label:"{label}"'

        search_query = f"repo:{self._ctx.repo}{label_filter}"

        after: str | None = None
        while True:
            response = await self.client.graphql(
                SEARCH_ISSUES,
                variables={"query": search_query, "after": after},
            )

            search_data = response.get("data", {}).get("search", {})
            nodes = search_data.get("nodes", [])

            for issue in nodes:
                item = GitHubItem(
                    id=issue.get("id", ""),
                    key=f"#{issue.get('number')}",
                    url=issue.get("url", ""),
                    title=issue.get("title", ""),
                    body=issue.get("body", ""),
                    item_type=None,  # GitHub API doesn't expose type directly in search
                    parent_id=None,  # Would need additional query
                    labels=[label.get("name", "") for label in issue.get("labels", {}).get("nodes", [])],
                    provider=self,
                    ctx=self._ctx,
                )
                items.append(item)

            page_info = search_data.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            after = page_info.get("endCursor")

        return items

    # ---- CRUD ----

    async def create_item(self, input: CreateItemInput) -> Item:
        """Create a new work item atomically.

        Handles:
        - Issue creation
        - Type assignment (if needed)
        - Field settings (status, priority, size, iteration)
        - Adding to project board (if configured)

        Args:
            input: Item creation data

        Returns:
            Created GitHubItem
        """
        if not self._ctx:
            raise ProviderError("Provider not initialized (not in async context)")

        # Create the issue
        owner, repo = self._ctx.repo.split("/", 1)
        label_ids = [self._ctx.repo_label_id] if self._ctx.repo_label_id else []

        response = await self.client.graphql(
            CREATE_ISSUE,
            variables={
                "repositoryId": self._ctx.repo_id,
                "title": input.title,
                "body": input.body or "",
                "issueTypeId": self._ctx.issue_type_ids.get("Task"),
                "labelIds": label_ids,
            },
        )

        issue_data = response.get("data", {}).get("createIssue", {}).get("issue", {})
        if not issue_data:
            raise ProviderError("Failed to create issue")

        issue_id = issue_data.get("id")
        issue_number = issue_data.get("number")
        issue_url = issue_data.get("url", f"https://github.com/{self._ctx.repo}/issues/{issue_number}")

        # Set issue type based on item_type
        if input.item_type and input.item_type.value.capitalize() in self._ctx.issue_type_ids:
            type_id = self._ctx.issue_type_ids[input.item_type.value.capitalize()]
            await self.client.graphql(
                UPDATE_ISSUE_TYPE,
                variables={"issueId": issue_id, "issueTypeId": type_id},
            )

        # Add to project if configured
        project_item_id: str | None = None
        if self._ctx.project_id:
            response = await self.client.graphql(
                ADD_PROJECT_ITEM,
                variables={"projectId": self._ctx.project_id, "contentId": issue_id},
            )
            project_item_data = response.get("data", {}).get("addProjectV2ItemById", {})
            project_item_id = project_item_data.get("item", {}).get("id")

            # Set project fields if we have the item in the project
            if project_item_id:
                if self._ctx.status_field:
                    await self.client.graphql(
                        UPDATE_PROJECT_FIELD,
                        variables={
                            "projectId": self._ctx.project_id,
                            "itemId": project_item_id,
                            "fieldId": self._ctx.status_field.field_id,
                            "value": self._ctx.status_field.value.model_dump(exclude_none=True),
                        },
                    )

                if self._ctx.priority_field:
                    await self.client.graphql(
                        UPDATE_PROJECT_FIELD,
                        variables={
                            "projectId": self._ctx.project_id,
                            "itemId": project_item_id,
                            "fieldId": self._ctx.priority_field.field_id,
                            "value": self._ctx.priority_field.value.model_dump(exclude_none=True),
                        },
                    )

                if self._ctx.iteration_field:
                    await self.client.graphql(
                        UPDATE_PROJECT_FIELD,
                        variables={
                            "projectId": self._ctx.project_id,
                            "itemId": project_item_id,
                            "fieldId": self._ctx.iteration_field.field_id,
                            "value": self._ctx.iteration_field.value.model_dump(exclude_none=True),
                        },
                    )

                # Set size if configured
                if input.size and self._ctx.size_field_id and self._ctx.size_options:
                    size_option_id = resolve_option_id(self._ctx.size_options, input.size)
                    if size_option_id:
                        await self.client.graphql(
                            UPDATE_PROJECT_FIELD,
                            variables={
                                "projectId": self._ctx.project_id,
                                "itemId": project_item_id,
                                "fieldId": self._ctx.size_field_id,
                                "value": {"single_select_option_id": size_option_id},
                            },
                        )

        return GitHubItem(
            id=issue_id,
            key=f"#{issue_number}",
            url=issue_url,
            title=input.title,
            body=input.body or "",
            item_type=input.item_type,
            parent_id=None,
            labels=input.labels or [],
            provider=self,
            ctx=self._ctx,
        )

    async def update_item(self, item_id: str, input: UpdateItemInput) -> Item:
        """Update an existing work item.

        Args:
            item_id: Opaque provider ID
            input: Fields to update

        Returns:
            Updated GitHubItem
        """
        if not self._ctx:
            raise ProviderError("Provider not initialized (not in async context)")

        # Stub: In a full implementation, would fetch and update the item
        raise NotImplementedError("update_item not yet implemented")

    async def get_item(self, item_id: str) -> Item:
        """Fetch a single work item by provider ID.

        Args:
            item_id: Opaque provider ID

        Returns:
            GitHubItem

        Raises:
            ProviderError: If not found or fetch fails
        """
        if not self._ctx:
            raise ProviderError("Provider not initialized (not in async context)")

        # Stub: In a full implementation, would fetch the item by ID
        raise NotImplementedError("get_item not yet implemented")

    async def delete_item(self, item_id: str) -> None:
        """Delete a work item.

        Args:
            item_id: Opaque provider ID

        Raises:
            ProviderError: If deletion fails
        """
        if not self._ctx:
            raise ProviderError("Provider not initialized (not in async context)")

        # Stub: In a full implementation, would delete the item
        raise NotImplementedError("delete_item not yet implemented")

    # ---- Internal relation helpers (called by GitHubItem) ----

    async def _set_item_parent(self, child: GitHubItem, parent: GitHubItem) -> None:
        """Internal: Set parent via sub-issue API."""
        # Stub implementation
        pass

    async def _add_item_child(self, parent: GitHubItem, child: GitHubItem) -> None:
        """Internal: Add child via sub-issue API."""
        # Stub implementation
        pass

    async def _remove_item_child(self, parent: GitHubItem, child: GitHubItem) -> None:
        """Internal: Remove child via sub-issue API."""
        # Stub implementation
        pass

    async def _get_item_children(self, parent: GitHubItem) -> list[GitHubItem]:
        """Internal: Get children from GitHub."""
        # Stub implementation
        return []

    async def _add_item_dependency(self, item: GitHubItem, blocker: GitHubItem) -> None:
        """Internal: Add blocking dependency via GitHub API."""
        # Stub implementation
        pass

    async def _remove_item_dependency(self, item: GitHubItem, blocker: GitHubItem) -> None:
        """Internal: Remove blocking dependency via GitHub API."""
        # Stub implementation
        pass

    async def _get_item_dependencies(self, item: GitHubItem) -> list[GitHubItem]:
        """Internal: Get dependencies from GitHub."""
        # Stub implementation
        return []
