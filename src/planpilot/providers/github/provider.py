"""GitHub provider implementation for planpilot (refactored for new Provider ABC).

Implements the thin CRUD layer Provider ABC using gh CLI and GraphQL.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, TYPE_CHECKING

from planpilot.exceptions import ProjectURLError, ProviderError
from planpilot.models.item import CreateItemInput, ItemSearchFilters, ItemType, TargetContext, UpdateItemInput
from planpilot.models.project import FieldConfig, FieldValue, ResolvedField
from planpilot.providers.base import Provider
from planpilot.providers.github.client import GhClient
from planpilot.providers.github.item import GitHubItem
from planpilot.providers.github.mapper import (
    parse_markers,
    parse_project_url,
    resolve_option_id,
)
from planpilot.providers.github.models import ProjectContext, RepoContext
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
    from planpilot.models.item import Item

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
        issue_types = (repo_data.get("issueTypes") or {}).get("nodes", [])
        labels = (repo_data.get("labels") or {}).get("nodes", [])

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
        # GhClient doesn't hold persistent connections (shells out to gh CLI)
        # so there's nothing to clean up
        pass

    # ---- Search ----

    async def search_items(self, filters: ItemSearchFilters) -> list[Item]:
        """Search for work items matching filters.

        Supports filtering by labels and body text (via GitHub search syntax).

        Args:
            filters: Search filters (labels, body_contains, etc.)

        Returns:
            List of GitHubItem instances
        """
        if not self._ctx:
            raise ProviderError("Provider not initialized (not in async context)")

        items: list[Item] = []

        # Build search query using GitHub search syntax
        search_query = f"repo:{self._ctx.repo} is:issue"

        if filters.labels:
            for label in filters.labels:
                search_query += f' label:"{label}"'

        if filters.body_contains:
            search_query += f' "{filters.body_contains}" in:body'

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

        # Use the base label resolved in __aenter__
        label_ids = [self._ctx.repo_label_id] if self._ctx.repo_label_id else []
        
        # Determine issue type ID
        type_name = input.item_type.value.capitalize() if input.item_type else "Task"
        type_id = self._ctx.issue_type_ids.get(type_name)

        response = await self.client.graphql(
            CREATE_ISSUE,
            variables={
                "repositoryId": self._ctx.repo_id,
                "title": input.title,
                "body": input.body or "",
                "issueTypeId": type_id,
                "labelIds": label_ids,
            },
        )

        issue_data = response.get("data", {}).get("createIssue", {}).get("issue", {})
        if not issue_data:
            raise ProviderError("Failed to create issue")

        issue_id = issue_data.get("id")
        issue_number = issue_data.get("number")
        issue_url = issue_data.get("url", f"https://github.com/{self._ctx.repo}/issues/{issue_number}")

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
            item_id: Opaque provider ID (GitHub node ID)
            input: Fields to update

        Returns:
            Updated GitHubItem

        Raises:
            ProviderError: If update fails
        """
        if not self._ctx:
            raise ProviderError("Provider not initialized (not in async context)")

        # For now, we only support updating body/title
        # GitHub's updateIssue mutation updates both
        if input.title or input.body:
            # Get current issue details first
            response = await self.client.graphql(
                """
                query($id: ID!) {
                  node(id: $id) {
                    ... on Issue {
                      id
                      number
                      title
                      body
                      url
                      repository {
                        nameWithOwner
                      }
                    }
                  }
                }
                """,
                variables={"id": item_id},
            )

            issue = response.get("data", {}).get("node", {})
            if not issue:
                raise ProviderError(f"Issue not found: {item_id}")

            title = input.title or issue.get("title", "")
            body = input.body or issue.get("body", "")

            # Update the issue
            await self.client.graphql(
                """
                mutation($id: ID!, $title: String!, $body: String) {
                  updateIssue(input: {id: $id, title: $title, body: $body}) {
                    issue {
                      id
                      number
                      title
                      body
                      url
                    }
                  }
                }
                """,
                variables={"id": item_id, "title": title, "body": body},
            )

        # Fetch updated item
        response = await self.client.graphql(
            """
            query($id: ID!) {
              node(id: $id) {
                ... on Issue {
                  id
                  number
                  title
                  body
                  url
                }
              }
            }
            """,
            variables={"id": item_id},
        )

        issue = response.get("data", {}).get("node", {})
        if not issue:
            raise ProviderError(f"Updated issue not found: {item_id}")

        return GitHubItem(
            id=issue.get("id", ""),
            key=f"#{issue.get('number')}",
            url=issue.get("url", ""),
            title=issue.get("title", ""),
            body=issue.get("body", ""),
            item_type=None,
            parent_id=None,
            labels=[],
            provider=self,
            ctx=self._ctx,
        )

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
        try:
            await self.client.graphql(
                ADD_SUB_ISSUE,
                variables={"parentId": parent.id, "childId": child.id},
            )
        except ProviderError as e:
            logger.warning("Failed to set parent %s for item %s: %s", parent.id, child.id, e)

    async def _add_item_child(self, parent: GitHubItem, child: GitHubItem) -> None:
        """Internal: Add child via sub-issue API."""
        # Same as set_parent from child's perspective
        await self._set_item_parent(child, parent)

    async def _remove_item_child(self, parent: GitHubItem, child: GitHubItem) -> None:
        """Internal: Remove child via sub-issue API."""
        # GitHub doesn't have a direct "remove sub-issue" mutation
        # For now, log and skip (idempotent)
        logger.warning("Remove child not yet implemented for GitHub (idempotent skip)")

    async def _get_item_children(self, parent: GitHubItem) -> list[GitHubItem]:
        """Internal: Get children from GitHub."""
        if not self._ctx:
            logger.warning("Provider not initialized for get_children")
            return []
        
        try:
            response = await self.client.graphql(
                """
                query($id: ID!) {
                  node(id: $id) {
                    ... on Issue {
                      children(first: 50) {
                        nodes {
                          id
                          number
                          title
                          body
                          url
                        }
                      }
                    }
                  }
                }
                """,
                variables={"id": parent.id},
            )
            children_data = response.get("data", {}).get("node", {}).get("children", {}).get("nodes", [])
            return [
                GitHubItem(
                    id=child.get("id", ""),
                    key=f"#{child.get('number')}",
                    url=child.get("url", ""),
                    title=child.get("title", ""),
                    body=child.get("body", ""),
                    item_type=None,
                    parent_id=parent.id,
                    labels=[],
                    provider=self,
                    ctx=self._ctx,
                )
                for child in children_data
            ]
        except (ProviderError, KeyError, TypeError) as e:
            logger.warning("Failed to get children for %s: %s", parent.id, e)
            return []

    async def _add_item_dependency(self, item: GitHubItem, blocker: GitHubItem) -> None:
        """Internal: Add blocking dependency via GitHub API."""
        try:
            await self.client.graphql(
                ADD_BLOCKED_BY,
                variables={"subjectId": item.id, "blockerId": blocker.id},
            )
        except ProviderError as e:
            logger.warning("Failed to add dependency %s -> %s: %s", blocker.id, item.id, e)

    async def _remove_item_dependency(self, item: GitHubItem, blocker: GitHubItem) -> None:
        """Internal: Remove blocking dependency via GitHub API."""
        # GitHub doesn't have a direct "remove blocked by" mutation
        # For now, log and skip (idempotent)
        logger.warning("Remove dependency not yet implemented for GitHub (idempotent skip)")

    async def _get_item_dependencies(self, item: GitHubItem) -> list[GitHubItem]:
        """Internal: Get dependencies from GitHub."""
        try:
            response = await self.client.graphql(
                FETCH_ISSUE_RELATIONS,
                variables={"ids": [item.id]},
            )
            # Parse response for blockers (blocked_by relations)
            # This is complex; for now return empty to indicate feature not yet implemented
            logger.debug("Get dependencies not yet fully implemented for GitHub")
            return []
        except (ProviderError, KeyError, TypeError) as e:
            logger.warning("Failed to get dependencies for %s: %s", item.id, e)
            return []
