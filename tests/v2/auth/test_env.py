import pytest

from planpilot_v2.auth.resolvers.env import EnvTokenResolver
from planpilot_v2.contracts.exceptions import AuthenticationError


@pytest.mark.asyncio
async def test_env_token_resolver_returns_token_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok_123")

    resolver = EnvTokenResolver()

    assert await resolver.resolve() == "tok_123"


@pytest.mark.asyncio
async def test_env_token_resolver_raises_when_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    resolver = EnvTokenResolver()

    with pytest.raises(AuthenticationError):
        await resolver.resolve()


@pytest.mark.asyncio
async def test_env_token_resolver_raises_when_env_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "   ")

    resolver = EnvTokenResolver()

    with pytest.raises(AuthenticationError):
        await resolver.resolve()
