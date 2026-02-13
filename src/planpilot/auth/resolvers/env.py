"""Environment token resolver."""

from __future__ import annotations

import os

from planpilot.auth.base import TokenResolver
from planpilot.core.contracts.exceptions import AuthenticationError


class EnvTokenResolver(TokenResolver):
    async def resolve(self) -> str:
        token = (os.getenv("GITHUB_TOKEN") or "").strip()
        if not token:
            raise AuthenticationError("GITHUB_TOKEN is not set or empty")
        return token
