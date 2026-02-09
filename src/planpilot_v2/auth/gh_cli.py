"""GitHub CLI token resolver."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from planpilot_v2.auth.base import TokenResolver
from planpilot_v2.contracts.exceptions import AuthenticationError


@dataclass(frozen=True)
class GhCliTokenResolver(TokenResolver):
    hostname: str = "github.com"

    async def resolve(self) -> str:
        try:
            process = await asyncio.create_subprocess_exec(
                "gh",
                "auth",
                "token",
                "--hostname",
                self.hostname,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise AuthenticationError(f"Failed to execute gh CLI: {exc}") from exc

        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            details = stderr.decode(errors="replace").strip()
            message = f"gh auth token failed for host {self.hostname}"
            if details:
                message = f"{message}: {details}"
            raise AuthenticationError(message)

        token = stdout.decode(errors="replace").strip()
        if not token:
            raise AuthenticationError(f"gh auth token returned an empty token for host {self.hostname}")

        return token
