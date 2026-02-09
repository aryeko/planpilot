"""Minimal generated-client compatible wrapper.

This module is a placeholder scaffold for ariadne-codegen output in local development.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


class GitHubGraphQLClient:
    """Thin adapter around an async GraphQL callable."""

    def __init__(self, caller: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]) -> None:
        self._caller = caller

    async def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._caller(query, variables or {})
