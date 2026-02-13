"""Token resolver factory."""

from __future__ import annotations

from urllib.parse import urlparse

from planpilot.auth.base import TokenResolver
from planpilot.auth.resolvers.env import EnvTokenResolver
from planpilot.auth.resolvers.gh_cli import GhCliTokenResolver
from planpilot.auth.resolvers.static import StaticTokenResolver
from planpilot.core.contracts.config import PlanPilotConfig
from planpilot.core.contracts.exceptions import ConfigError

RESOLVERS: dict[str, type[TokenResolver]] = {
    "gh-cli": GhCliTokenResolver,
    "env": EnvTokenResolver,
    "token": StaticTokenResolver,
}


def _hostname_from_target(target: str) -> str:
    raw = target.strip()
    if not raw:
        return "github.com"

    if "://" in raw:
        parsed = urlparse(raw)
        if parsed.hostname:
            return parsed.hostname

    prefix, separator, remainder = raw.partition(":")
    if separator and "@" in prefix and "/" in remainder:
        _, _, host = prefix.rpartition("@")
        if host:
            return host

    candidate = raw.split("/", 1)[0]
    parsed_candidate = urlparse(f"//{candidate}")
    if parsed_candidate.hostname and "." in parsed_candidate.hostname:
        return parsed_candidate.hostname

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
