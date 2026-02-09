"""Factory for creating provider instances.

Decouples provider selection from provider implementation. CLI uses this
factory to instantiate providers by name, without importing concrete providers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from planpilot.providers.base import Provider


# Registry mapping provider names to their classes
_REGISTRY: dict[str, type[Provider]] = {}


def register(name: str, provider_cls: type[Provider]) -> None:
    """Register a provider class by name.

    Args:
        name: Provider name (e.g. "github").
        provider_cls: Provider class that implements the Provider ABC.
    """
    _REGISTRY[name] = provider_cls


def create_provider(
    name: str,
    *,
    target: str,
    board_url: str | None = None,
    label: str | None = None,
    field_config: FieldConfig | None = None,
    **kwargs: object,
) -> Provider:
    """Create a provider instance by name.

    The returned provider is an async context manager. Use it like:

        async with create_provider("github", target="owner/repo", ...) as provider:
            items = await provider.search_items(...)

    Args:
        name: Provider name (must be registered).
        target: Target designation (e.g. "owner/repo").
        board_url: Board URL (optional).
        label: Label name (optional).
        field_config: Field configuration (optional).
        **kwargs: Additional provider-specific arguments.

    Returns:
        Provider instance (async context manager).

    Raises:
        ValueError: If the provider name is not registered.
    """
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY.keys())) or "(none registered)"
        raise ValueError(
            f"Unknown provider: {name!r}. Available: {available}"
        )

    provider_cls = _REGISTRY[name]
    return provider_cls(
        target=target,
        board_url=board_url,
        label=label,
        field_config=field_config,
        **kwargs,
    )
