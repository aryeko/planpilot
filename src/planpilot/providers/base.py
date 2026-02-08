"""Abstract base class for issue-tracking / project-management providers.

Every concrete provider (GitHub, Jira, Linear, …) must implement this
interface so the :class:`~planpilot.sync.engine.SyncEngine` can orchestrate
syncs without knowing *which* system it talks to.

All methods are ``async``; providers that wrap a synchronous transport
(e.g. the ``gh`` CLI) should use ``asyncio.create_subprocess_exec`` or
``asyncio.to_thread``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from planpilot.models.project import (
    CreateIssueInput,
    ExistingIssue,
    FieldConfig,
    FieldValue,
    IssueRef,
    ProjectContext,
    RelationMap,
    RepoContext,
)


class Provider(ABC):
    """Abstract provider for issue tracking and project management systems."""

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    @abstractmethod
    async def check_auth(self) -> None:
        """Verify the current session is authenticated.

        Raises:
            AuthenticationError: If authentication fails.
        """

    # ------------------------------------------------------------------
    # Context resolution
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_repo_context(self, repo: str, label: str) -> RepoContext:
        """Fetch repository metadata, issue types, and ensure *label* exists.

        Args:
            repo: Repository identifier (e.g. ``"owner/repo"``).
            label: Label name to ensure exists.

        Returns:
            Resolved :class:`RepoContext`.
        """

    @abstractmethod
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

    # ------------------------------------------------------------------
    # Issues
    # ------------------------------------------------------------------

    @abstractmethod
    async def search_issues(self, repo: str, plan_id: str, label: str) -> list[ExistingIssue]:
        """Search for issues belonging to *plan_id*.

        Args:
            repo: Repository identifier.
            plan_id: Deterministic plan hash embedded in issue bodies.
            label: Label name to filter search results.

        Returns:
            List of matching :class:`ExistingIssue` instances.
        """

    @abstractmethod
    def build_issue_map(
        self, existing_issues: list[ExistingIssue], plan_id: str
    ) -> dict[str, dict[str, dict[str, Any]]]:
        """Build a mapping of entity IDs to issue metadata, filtered by plan_id.

        Args:
            existing_issues: Raw issue instances from the search API.
            plan_id: Only include issues matching this plan_id.

        Returns:
            Nested dict: ``{"epics": {id: {id, number}}, "stories": ..., "tasks": ...}``.
        """

    @abstractmethod
    def resolve_option_id(self, options: list[dict[str, str]], name: str | None) -> str | None:
        """Find the option ID matching *name* (case-insensitive).

        Args:
            options: List of ``{"id": ..., "name": ...}`` dicts.
            name: Option name to search for.

        Returns:
            The matching option ID, or None.
        """

    @abstractmethod
    async def create_issue(self, issue_input: CreateIssueInput) -> IssueRef:
        """Create a new issue.

        Args:
            issue_input: All data required to create the issue.

        Returns:
            Newly-created :class:`IssueRef`.

        Raises:
            ProviderError: If the creation fails.
        """

    @abstractmethod
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

    @abstractmethod
    async def set_issue_type(self, issue_id: str, type_id: str) -> None:
        """Set the issue type (e.g. Epic, Story, Task).

        Args:
            issue_id: Issue node ID.
            type_id: Issue-type node ID.
        """

    # ------------------------------------------------------------------
    # Project board
    # ------------------------------------------------------------------

    @abstractmethod
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

    @abstractmethod
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

    # ------------------------------------------------------------------
    # Relations
    # ------------------------------------------------------------------

    @abstractmethod
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

    @abstractmethod
    async def add_sub_issue(self, parent_id: str, child_id: str) -> None:
        """Create a parent → child sub-issue relationship.

        Args:
            parent_id: Parent issue node ID.
            child_id: Child issue node ID.
        """

    @abstractmethod
    async def add_blocked_by(self, issue_id: str, blocker_id: str) -> None:
        """Record that *issue_id* is blocked by *blocker_id*.

        Args:
            issue_id: The blocked issue's node ID.
            blocker_id: The blocking issue's node ID.
        """
