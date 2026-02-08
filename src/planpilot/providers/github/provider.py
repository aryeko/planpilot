"""GitHub provider implementation for planpilot."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from planpilot.exceptions import ProjectURLError, ProviderError
from planpilot.models.project import (
    CreateIssueInput,
    ExistingIssue,
    FieldConfig,
    FieldValue,
    IssueRef,
    ProjectContext,
    RelationMap,
    RepoContext,
    ResolvedField,
)
from planpilot.providers.base import Provider
from planpilot.providers.github.client import GhClient
from planpilot.providers.github.mapper import (
    build_blocked_by_map,
    build_parent_map,
    build_project_item_map,
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

logger = logging.getLogger(__name__)


class GitHubProvider(Provider):
    """GitHub provider implementation using the gh CLI."""

    def __init__(self, client: GhClient) -> None:
        """Initialize the GitHub provider.

        Args:
            client: The GitHub client to use for API calls.
        """
        self.client = client

    async def check_auth(self) -> None:
        """Verify the current session is authenticated.

        Raises:
            AuthenticationError: If authentication fails.
        """
        await self.client.check_auth()

    async def get_repo_context(self, repo: str, label: str) -> RepoContext:
        """Fetch repository metadata, issue types, and ensure *label* exists.

        Args:
            repo: Repository identifier (e.g. ``"owner/repo"``).
            label: Label name to ensure exists.

        Returns:
            Resolved :class:`RepoContext`.
        """
        owner, name = repo.split("/", 1)

        # Fetch repo data
        response = await self.client.graphql(
            FETCH_REPO,
            variables={"owner": owner, "name": name, "label": label},
        )

        repo_data = response.get("data", {}).get("repository")
        if not repo_data:
            raise ProviderError(f"Repository {repo} not found")

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

        # Check if label exists
        label_id: str | None = None
        if labels:
            label_id = labels[0].get("id")
        else:
            # Label not found, try to create it
            logger.info(f"Label '{label}' not found in {repo}, attempting to create it")
            try:
                await self.client.run(
                    ["label", "create", label, "--repo", repo],
                    check=True,
                )
                # Re-fetch to get the label ID
                response = await self.client.graphql(
                    FETCH_REPO,
                    variables={"owner": owner, "name": name, "label": label},
                )
                repo_data = response.get("data", {}).get("repository", {})
                labels = repo_data.get("labels", {}).get("nodes", [])
                if labels:
                    label_id = labels[0].get("id")
            except ProviderError as e:
                logger.warning(f"Failed to create label '{label}': {e}")
            except Exception as e:
                logger.warning(f"Unexpected error creating label '{label}': {type(e).__name__}: {e}")

        return RepoContext(
            repo_id=repo_id,
            label_id=label_id,
            issue_type_ids=issue_type_ids,
        )

    async def get_project_context(
        self,
        project_url: str,
        field_config: FieldConfig,
    ) -> ProjectContext | None:
        """Fetch project board metadata and resolve field IDs.

        Args:
            project_url: Full URL to the project board.
            field_config: User-specified field preferences.

        Returns:
            Resolved :class:`ProjectContext`, or *None* if unavailable.
        """
        try:
            org, number = parse_project_url(project_url)
        except ProjectURLError:
            logger.error(f"Invalid project URL: {project_url}")
            return None

        try:
            # Fetch project data
            response = await self.client.graphql(
                FETCH_PROJECT,
                variables={"org": org, "number": number},
            )

            project_data = response.get("data", {}).get("organization", {}).get("projectV2")
            if not project_data:
                logger.error(f"Project {org}/{number} not found")
                return None

            project_id = project_data.get("id")
            fields = project_data.get("fields", {}).get("nodes", [])

            # Resolve fields
            status_field: ResolvedField | None = None
            priority_field: ResolvedField | None = None
            iteration_field: ResolvedField | None = None
            size_field_id: str | None = None
            size_options: list[dict[str, str]] = []

            for field in fields:
                field_id = field.get("id")
                field_name = field.get("name", "")

                # Status field
                if field_name == "Status" and "options" in field:
                    options = field.get("options", [])
                    option_id = resolve_option_id(options, field_config.status)
                    if option_id:
                        status_field = ResolvedField(
                            field_id=field_id,
                            value=FieldValue(single_select_option_id=option_id),
                        )

                # Priority field
                if field_name == "Priority" and "options" in field:
                    options = field.get("options", [])
                    option_id = resolve_option_id(options, field_config.priority)
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

                    if field_config.iteration == "active":
                        # Find active iteration
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
                        # Find iteration by name
                        for it in iterations:
                            if it.get("title", "").lower() == field_config.iteration.lower():
                                iteration_id = it.get("id")
                                break

                    if iteration_id:
                        iteration_field = ResolvedField(
                            field_id=field_id,
                            value=FieldValue(iteration_id=iteration_id),
                        )

                # Size field
                if field_name == field_config.size_field and "options" in field:
                    size_field_id = field_id
                    size_options = [
                        {"id": opt.get("id"), "name": opt.get("name")}
                        for opt in field.get("options", [])
                        if opt.get("id") and opt.get("name")
                    ]

            # Fetch project items with pagination
            item_map: dict[str, str] = {}
            after: str | None = None
            while True:
                response = await self.client.graphql(
                    FETCH_PROJECT_ITEMS,
                    variables={"projectId": project_id, "after": after},
                )

                node_data = response.get("data", {}).get("node", {})
                items_data = node_data.get("items", {})
                nodes = items_data.get("nodes", [])
                page_info = items_data.get("pageInfo", {})

                item_map.update(build_project_item_map(nodes))

                if not page_info.get("hasNextPage"):
                    break
                after = page_info.get("endCursor")

            return ProjectContext(
                project_id=project_id,
                status_field=status_field,
                priority_field=priority_field,
                iteration_field=iteration_field,
                size_field_id=size_field_id,
                size_options=size_options,
                item_map=item_map,
            )

        except Exception as e:
            logger.error(f"Failed to fetch project context: {e}", exc_info=True)
            return None

    async def search_issues(self, repo: str, plan_id: str) -> list[ExistingIssue]:
        """Search for issues belonging to *plan_id*.

        Args:
            repo: Repository identifier.
            plan_id: Deterministic plan hash embedded in issue bodies.

        Returns:
            List of matching :class:`ExistingIssue` instances.
        """
        search_query = f'repo:{repo} label:planpilot "{plan_id}" in:body'
        issues: list[ExistingIssue] = []
        after: str | None = None

        while True:
            response = await self.client.graphql(
                SEARCH_ISSUES,
                variables={"searchQuery": search_query, "after": after},
            )

            search_data = response.get("data", {}).get("search", {})
            nodes = search_data.get("nodes", [])
            page_info = search_data.get("pageInfo", {})

            for node in nodes:
                issues.append(
                    ExistingIssue(
                        id=node.get("id", ""),
                        number=node.get("number", 0),
                        body=node.get("body", ""),
                    )
                )

            if not page_info.get("hasNextPage"):
                break
            after = page_info.get("endCursor")

        return issues

    async def create_issue(self, issue_input: CreateIssueInput) -> IssueRef:
        """Create a new issue.

        Args:
            issue_input: All data required to create the issue.

        Returns:
            Newly-created :class:`IssueRef`.

        Raises:
            ProviderError: If the creation fails.
        """
        # Build the input object as JSON
        input_obj = {
            "repositoryId": issue_input.repo_id,
            "title": issue_input.title,
            "body": issue_input.body,
        }
        if issue_input.label_ids:
            input_obj["labelIds"] = issue_input.label_ids

        input_json = json.dumps(input_obj)

        # Use graphql_raw with -F flags
        args = [
            "api",
            "graphql",
            "-f",
            f"query={CREATE_ISSUE}",
            "-F",
            f"input={input_json}",
        ]

        try:
            response = await self.client.graphql_raw(args)
            issue_data = response.get("data", {}).get("createIssue", {}).get("issue", {})
            if not issue_data:
                raise ProviderError("Failed to create issue: no issue data returned")

            return IssueRef(
                id=issue_data.get("id", ""),
                number=issue_data.get("number", 0),
                url=issue_data.get("url", ""),
            )
        except Exception as e:
            raise ProviderError(f"Failed to create issue: {e}") from e

    async def update_issue(
        self,
        repo: str,
        number: int,
        title: str,
        body: str,
    ) -> None:
        """Update an existing issue's title and body.

        Args:
            repo: Repository identifier.
            number: Issue number.
            title: New title.
            body: New body (markdown).
        """
        await self.client.run(
            [
                "issue",
                "edit",
                str(number),
                "--repo",
                repo,
                "--title",
                title,
                "--body",
                body,
            ],
            check=True,
        )

    async def set_issue_type(self, issue_id: str, type_id: str) -> None:
        """Set the issue type (e.g. Epic, Story, Task).

        Args:
            issue_id: Issue node ID.
            type_id: Issue-type node ID.
        """
        await self.client.graphql(
            UPDATE_ISSUE_TYPE,
            variables={"id": issue_id, "issueTypeId": type_id},
        )

    async def add_to_project(
        self,
        project_id: str,
        issue_id: str,
    ) -> str | None:
        """Add an issue to a project board.

        Args:
            project_id: Project node ID.
            issue_id: Issue node ID.

        Returns:
            The project-item ID, or *None* on failure.
        """
        try:
            response = await self.client.graphql(
                ADD_PROJECT_ITEM,
                variables={"projectId": project_id, "contentId": issue_id},
            )
            item_data = response.get("data", {}).get("addProjectV2ItemById", {}).get("item", {})
            return item_data.get("id")
        except Exception as e:
            logger.warning(f"Failed to add issue to project: {e}")
            return None

    async def set_project_field(
        self,
        project_id: str,
        item_id: str,
        field_id: str,
        value: FieldValue,
    ) -> None:
        """Set a single field value on a project item.

        Args:
            project_id: Project node ID.
            item_id: Project-item ID.
            field_id: Field node ID.
            value: The value to set.
        """
        # Build the value object
        value_obj: dict[str, Any] = {}
        if value.single_select_option_id:
            value_obj["singleSelectOptionId"] = value.single_select_option_id
        elif value.iteration_id:
            value_obj["iterationId"] = value.iteration_id
        elif value.text is not None:
            value_obj["text"] = value.text
        elif value.number is not None:
            value_obj["number"] = value.number

        value_json = json.dumps(value_obj)

        # Use graphql_raw with -F flags
        args = [
            "api",
            "graphql",
            "-f",
            f"query={UPDATE_PROJECT_FIELD}",
            "-F",
            f"projectId={project_id}",
            "-F",
            f"itemId={item_id}",
            "-F",
            f"fieldId={field_id}",
            "-F",
            f"value={value_json}",
        ]

        await self.client.graphql_raw(args)

    async def get_issue_relations(
        self,
        issue_ids: list[str],
    ) -> RelationMap:
        """Fetch parent and blocked-by relations for the given issues.

        Args:
            issue_ids: Issue node IDs to query.

        Returns:
            :class:`RelationMap` with parent and blocked-by data.
        """
        # Note: IDs come from trusted sources (GitHub API), so inlining them
        # into the query string is safe from a GraphQL injection perspective.
        # However, we batch into groups of 50 to avoid query size limits.

        all_nodes: list[dict[str, Any]] = []
        batch_size = 50

        for i in range(0, len(issue_ids), batch_size):
            batch = issue_ids[i : i + batch_size]
            # Inline IDs into query string - replace the variable with actual IDs
            ids_str = json.dumps(batch)
            # Replace the variable declaration and usage with inline values
            query = FETCH_ISSUE_RELATIONS.replace("query($ids: [ID!]!)", "query").replace(
                "nodes(ids: $ids)", f"nodes(ids: {ids_str})"
            )

            args = [
                "api",
                "graphql",
                "-f",
                f"query={query}",
            ]

            response = await self.client.graphql_raw(args)
            nodes = response.get("data", {}).get("nodes", [])
            all_nodes.extend(nodes)

        return RelationMap(
            parents=build_parent_map(all_nodes),
            blocked_by=build_blocked_by_map(all_nodes),
        )

    async def add_sub_issue(self, parent_id: str, child_id: str) -> None:
        """Create a parent → child sub-issue relationship.

        Args:
            parent_id: Parent issue node ID.
            child_id: Child issue node ID.
        """
        await self.client.graphql(
            ADD_SUB_ISSUE,
            variables={"issueId": parent_id, "subIssueId": child_id},
        )

    async def add_blocked_by(self, issue_id: str, blocker_id: str) -> None:
        """Record that *issue_id* is blocked by *blocker_id*.

        Args:
            issue_id: The blocked issue's node ID.
            blocker_id: The blocking issue's node ID.
        """
        await self.client.graphql(
            ADD_BLOCKED_BY,
            variables={"issueId": issue_id, "blockingIssueId": blocker_id},
        )
