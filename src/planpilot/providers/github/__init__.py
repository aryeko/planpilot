"""GitHub provider adapter using the ``gh`` CLI."""

from planpilot.providers.factory import register
from planpilot.providers.github.provider import GitHubProvider

# Register GitHub provider
register("github", GitHubProvider)

__all__ = ["GitHubProvider"]
