from pathlib import Path

import pytest

from planpilot.core.auth.factory import create_token_resolver
from planpilot.core.auth.resolvers.env import EnvTokenResolver
from planpilot.core.auth.resolvers.gh_cli import GhCliTokenResolver
from planpilot.core.auth.resolvers.static import StaticTokenResolver
from planpilot.core.contracts.config import PlanPaths, PlanPilotConfig
from planpilot.core.contracts.exceptions import ConfigError


def _make_config(*, auth: str, target: str = "owner/repo", token: str | None = None) -> PlanPilotConfig:
    return PlanPilotConfig(
        provider="github",
        target=target,
        auth=auth,
        token=token,
        board_url="https://github.com/orgs/owner/projects/1",
        plan_paths=PlanPaths(unified=Path("plan.json")),
    )


def test_factory_creates_gh_cli_resolver() -> None:
    resolver = create_token_resolver(_make_config(auth="gh-cli"))

    assert isinstance(resolver, GhCliTokenResolver)


def test_factory_creates_env_resolver() -> None:
    resolver = create_token_resolver(_make_config(auth="env"))

    assert isinstance(resolver, EnvTokenResolver)


def test_factory_creates_static_resolver() -> None:
    resolver = create_token_resolver(_make_config(auth="token", token="tok_123"))

    assert isinstance(resolver, StaticTokenResolver)


def test_factory_raises_for_unknown_auth_mode() -> None:
    config = PlanPilotConfig.model_construct(
        provider="github",
        target="owner/repo",
        auth="unsupported",
        token=None,
        board_url="https://github.com/orgs/owner/projects/1",
        plan_paths=PlanPaths(unified=Path("plan.json")),
        validation_mode="strict",
        sync_path=Path("sync-map.json"),
        label="planpilot",
        max_concurrent=1,
    )

    with pytest.raises(ConfigError):
        create_token_resolver(config)


def test_factory_uses_hostname_from_target_for_gh_cli() -> None:
    resolver = create_token_resolver(_make_config(auth="gh-cli", target="https://github.example.com/org/repo"))

    assert isinstance(resolver, GhCliTokenResolver)
    assert resolver.hostname == "github.example.com"


def test_factory_defaults_to_github_for_blank_target() -> None:
    resolver = create_token_resolver(_make_config(auth="gh-cli", target="   "))

    assert isinstance(resolver, GhCliTokenResolver)
    assert resolver.hostname == "github.com"


@pytest.mark.parametrize(
    ("target", "expected_hostname"),
    [
        ("https://github.example.com:8443/org/repo", "github.example.com"),
        ("github.example.com:8443", "github.example.com"),
        ("git@github.example.com:owner/repo", "github.example.com"),
        ("github.example.com", "github.example.com"),
        ("owner/repo", "github.com"),
    ],
)
def test_factory_hostname_parsing_edge_cases(target: str, expected_hostname: str) -> None:
    resolver = create_token_resolver(_make_config(auth="gh-cli", target=target))

    assert isinstance(resolver, GhCliTokenResolver)
    assert resolver.hostname == expected_hostname


def test_factory_handles_malformed_scp_target() -> None:
    resolver = create_token_resolver(_make_config(auth="gh-cli", target="git@:owner/repo"))

    assert isinstance(resolver, GhCliTokenResolver)
    assert resolver.hostname == "github.com"
