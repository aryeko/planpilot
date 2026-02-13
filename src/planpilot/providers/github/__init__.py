"""GitHub provider implementation."""

from __future__ import annotations

__all__ = ["GitHubProvider"]


def __getattr__(name: str) -> object:
    if name == "GitHubProvider":
        from planpilot.core.providers.github.provider import GitHubProvider

        return GitHubProvider
    raise AttributeError(name)
