from pathlib import Path

import pytest

from planpilot_v2.auth.env import EnvTokenResolver
from planpilot_v2.auth.factory import create_token_resolver
from planpilot_v2.auth.gh_cli import GhCliTokenResolver
from planpilot_v2.auth.static import StaticTokenResolver
from planpilot_v2.contracts.config import PlanPaths, PlanPilotConfig
from planpilot_v2.contracts.exceptions import ConfigError


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
