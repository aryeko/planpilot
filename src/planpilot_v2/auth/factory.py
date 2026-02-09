"""Token resolver factory."""

from __future__ import annotations

from urllib.parse import urlparse

from planpilot_v2.auth.base import TokenResolver
from planpilot_v2.auth.env import EnvTokenResolver
from planpilot_v2.auth.gh_cli import GhCliTokenResolver
from planpilot_v2.auth.static import StaticTokenResolver
from planpilot_v2.contracts.config import PlanPilotConfig
from planpilot_v2.contracts.exceptions import ConfigError

RESOLVERS: dict[str, type[TokenResolver]] = {
    "gh-cli": GhCliTokenResolver,
    "env": EnvTokenResolver,
    "token": StaticTokenResolver,
}


def _hostname_from_target(target: str) -> str:
    raw = target.strip()
    if "://" in raw:
        parsed = urlparse(raw)
        if parsed.hostname:
            return parsed.hostname

    parts = raw.split("/")
    if len(parts) >= 2 and "." in parts[0]:
        return parts[0]
    if "/" not in raw and "." in raw:
        return raw

    return "github.com"


def create_token_resolver(config: PlanPilotConfig) -> TokenResolver:
    auth_mode = config.auth
    if auth_mode not in RESOLVERS:
        raise ConfigError(f"Unknown auth mode: {auth_mode}")

    if auth_mode == "gh-cli":
        return GhCliTokenResolver(hostname=_hostname_from_target(config.target))
    if auth_mode == "env":
        return EnvTokenResolver()
    return StaticTokenResolver(token=config.token or "")
