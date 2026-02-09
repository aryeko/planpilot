"""Provider factory."""

from __future__ import annotations

from typing import cast

from planpilot.contracts.config import FieldConfig
from planpilot.contracts.provider import Provider
from planpilot.providers.dry_run import DryRunProvider
from planpilot.providers.github.provider import GitHubProvider

PROVIDERS: dict[str, type[Provider]] = {
    "github": GitHubProvider,
    "dry-run": DryRunProvider,
}


def create_provider(
    name: str,
    *,
    target: str,
    token: str,
    board_url: str,
    label: str = "planpilot",
    field_config: FieldConfig | None = None,
    **kwargs: object,
) -> Provider:
    """Create a provider instance by name."""
    provider_cls = PROVIDERS.get(name)
    if provider_cls is None:
        raise ValueError(f"Unknown provider: {name}")

    if provider_cls is DryRunProvider:
        return provider_cls()

    github_provider_cls = cast(type[GitHubProvider], provider_cls)
    return github_provider_cls(
        target=target,
        token=token,
        board_url=board_url,
        label=label,
        field_config=field_config,
        **kwargs,
    )
