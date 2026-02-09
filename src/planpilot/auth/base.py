"""Auth resolver interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod


class TokenResolver(ABC):
    @abstractmethod
    async def resolve(self) -> str:
        """Resolve and return an authentication token."""
