import pytest

from planpilot.core.providers.dry_run import DryRunProvider
from planpilot.core.providers.factory import create_provider
from planpilot.core.providers.github.provider import GitHubProvider


def test_create_provider_for_github() -> None:
    provider = create_provider(
        "github",
        target="owner/repo",
        token="token",
        board_url="https://github.com/orgs/owner/projects/1",
    )

    assert isinstance(provider, GitHubProvider)


def test_create_provider_for_dry_run() -> None:
    provider = create_provider(
        "dry-run",
        target="owner/repo",
        token="token",
        board_url="https://github.com/orgs/owner/projects/1",
    )

    assert isinstance(provider, DryRunProvider)


def test_create_provider_raises_for_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unknown provider"):
        create_provider(
            "linear",
            target="owner/repo",
            token="token",
            board_url="https://github.com/orgs/owner/projects/1",
        )
