import pytest

from planpilot_v2.auth.static import StaticTokenResolver
from planpilot_v2.contracts.exceptions import AuthenticationError


@pytest.mark.asyncio
async def test_static_token_resolver_returns_token() -> None:
    resolver = StaticTokenResolver(token="tok_123")

    assert await resolver.resolve() == "tok_123"


@pytest.mark.asyncio
async def test_static_token_resolver_raises_for_empty_token() -> None:
    resolver = StaticTokenResolver(token="")

    with pytest.raises(AuthenticationError):
        await resolver.resolve()
