from __future__ import annotations

from typing import Any

import pytest

from planpilot_v2.auth.resolvers.gh_cli import GhCliTokenResolver
from planpilot_v2.contracts.exceptions import AuthenticationError


class _MockProcess:
    def __init__(self, returncode: int, stdout: bytes = b"", stderr: bytes = b"") -> None:
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self) -> tuple[bytes, bytes]:
        return self._stdout, self._stderr


@pytest.mark.asyncio
async def test_gh_cli_token_resolver_returns_token(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _mock_create_subprocess_exec(*args: Any, **kwargs: Any) -> _MockProcess:
        assert args == ("gh", "auth", "token", "--hostname", "github.com")
        return _MockProcess(returncode=0, stdout=b"tok_123\n")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _mock_create_subprocess_exec)

    resolver = GhCliTokenResolver()

    assert await resolver.resolve() == "tok_123"


@pytest.mark.asyncio
async def test_gh_cli_token_resolver_raises_on_subprocess_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _mock_create_subprocess_exec(*args: Any, **kwargs: Any) -> _MockProcess:
        return _MockProcess(returncode=1, stderr=b"not logged in")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _mock_create_subprocess_exec)

    resolver = GhCliTokenResolver()

    with pytest.raises(AuthenticationError):
        await resolver.resolve()


@pytest.mark.asyncio
async def test_gh_cli_token_resolver_raises_on_subprocess_error_without_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _mock_create_subprocess_exec(*args: Any, **kwargs: Any) -> _MockProcess:
        return _MockProcess(returncode=1, stderr=b"")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _mock_create_subprocess_exec)

    resolver = GhCliTokenResolver(hostname="github.enterprise.local")

    with pytest.raises(AuthenticationError, match=r"gh auth token failed for host github\.enterprise\.local"):
        await resolver.resolve()


@pytest.mark.asyncio
async def test_gh_cli_token_resolver_raises_when_subprocess_cannot_start(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _mock_create_subprocess_exec(*args: Any, **kwargs: Any) -> _MockProcess:
        raise OSError("gh missing")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _mock_create_subprocess_exec)

    resolver = GhCliTokenResolver()

    with pytest.raises(AuthenticationError, match="Failed to execute gh CLI"):
        await resolver.resolve()


@pytest.mark.asyncio
async def test_gh_cli_token_resolver_raises_on_empty_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _mock_create_subprocess_exec(*args: Any, **kwargs: Any) -> _MockProcess:
        return _MockProcess(returncode=0, stdout=b"  \n")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _mock_create_subprocess_exec)

    resolver = GhCliTokenResolver()

    with pytest.raises(AuthenticationError):
        await resolver.resolve()
