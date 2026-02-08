"""Async wrapper around the ``gh`` CLI."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from planpilot.exceptions import AuthenticationError, ProviderError

logger = logging.getLogger(__name__)


@dataclass
class CompletedProcess:
    """Result of a ``gh`` CLI invocation."""

    returncode: int
    stdout: str
    stderr: str


class GhClient:
    """Async wrapper around the ``gh`` CLI binary.

    All GitHub API calls are executed by shelling out to ``gh``.
    """

    async def run(self, args: list[str], *, check: bool = True) -> CompletedProcess:
        """Execute ``gh <args>`` asynchronously.

        Args:
            args: Arguments to pass to gh.
            check: If True, raise on non-zero exit.

        Returns:
            CompletedProcess with stdout, stderr, returncode.

        Raises:
            ProviderError: If check=True and the command fails.
        """
        cmd = ["gh", *args]
        logger.debug("Running: %s", " ".join(cmd))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()
        result = CompletedProcess(
            returncode=proc.returncode or 0,
            stdout=stdout_bytes.decode() if stdout_bytes else "",
            stderr=stderr_bytes.decode() if stderr_bytes else "",
        )
        if check and result.returncode != 0:
            raise ProviderError(f"gh command failed: {' '.join(cmd)}\n{result.stderr}")
        return result

    async def json(self, args: list[str]) -> Any:
        """Execute ``gh <args>`` and parse stdout as JSON.

        Returns:
            Parsed JSON, or None if stdout is empty.
        """
        result = await self.run(args)
        if not result.stdout.strip():
            return None
        return json.loads(result.stdout)

    async def graphql(self, query: str, variables: dict[str, str] | None = None) -> Any:
        """Execute a GraphQL query/mutation via ``gh api graphql``.

        Args:
            query: The GraphQL operation string.
            variables: Mapping of variable names to string values.

        Returns:
            Parsed JSON response.
        """
        args = ["api", "graphql", "-f", f"query={query}"]
        for key, value in (variables or {}).items():
            args.extend(["-f", f"{key}={value}"])
        return await self.json(args)

    async def graphql_raw(self, args: list[str]) -> Any:
        """Execute a raw gh api graphql call with pre-built args.

        Used for calls that need -F (typed) flags rather than -f.

        Args:
            args: Complete args list including "api", "graphql", etc.

        Returns:
            Parsed JSON response.
        """
        return await self.json(args)

    async def check_auth(self) -> None:
        """Verify gh authentication status.

        Raises:
            AuthenticationError: If not authenticated.
        """
        result = await self.run(["auth", "status"], check=False)
        if result.returncode != 0:
            raise AuthenticationError("GitHub authentication failed. Run `gh auth login` and retry.")
