"""Static token resolver."""

from __future__ import annotations

from dataclasses import dataclass

from planpilot.auth.base import TokenResolver
from planpilot.contracts.exceptions import AuthenticationError


@dataclass(frozen=True)
class StaticTokenResolver(TokenResolver):
    token: str

    async def resolve(self) -> str:
        resolved = self.token.strip()
        if not resolved:
            raise AuthenticationError("Static token is empty")
        return resolved
