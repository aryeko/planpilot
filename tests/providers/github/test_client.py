"""Tests for the GitHub client wrapper."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from planpilot.exceptions import AuthenticationError, ProviderError
from planpilot.providers.github.client import GhClient


@pytest.mark.asyncio
async def test_run_success():
    """Test that run() executes gh command successfully."""
    client = GhClient()
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"stdout", b"stderr"))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        result = await client.run(["repo", "view"])

    mock_exec.assert_called_once()
    assert result.returncode == 0
    assert result.stdout == "stdout"
    assert result.stderr == "stderr"


@pytest.mark.asyncio
async def test_run_with_check_raises_on_failure():
    """Test that run() raises ProviderError when check=True and command fails."""
    client = GhClient()
    mock_proc = AsyncMock()
    mock_proc.returncode = 1
    mock_proc.communicate = AsyncMock(return_value=(b"", b"error message"))

    with (
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        pytest.raises(ProviderError, match="gh command failed"),
    ):
        await client.run(["repo", "view"], check=True)


@pytest.mark.asyncio
async def test_run_without_check_returns_result_on_failure():
    """Test that run() returns result when check=False and command fails."""
    client = GhClient()
    mock_proc = AsyncMock()
    mock_proc.returncode = 1
    mock_proc.communicate = AsyncMock(return_value=(b"", b"error message"))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await client.run(["repo", "view"], check=False)

    assert result.returncode == 1
    assert result.stderr == "error message"


@pytest.mark.asyncio
async def test_json_parses_stdout():
    """Test that json() parses stdout as JSON."""
    client = GhClient()
    test_data = {"key": "value", "number": 42}
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(json.dumps(test_data).encode(), b""))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await client.json(["api", "graphql"])

    assert result == test_data


@pytest.mark.asyncio
async def test_json_returns_none_on_empty_stdout():
    """Test that json() returns None when stdout is empty."""
    client = GhClient()
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await client.json(["api", "graphql"])

    assert result is None


@pytest.mark.asyncio
async def test_json_returns_none_on_whitespace_only_stdout():
    """Test that json() returns None when stdout is only whitespace."""
    client = GhClient()
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"   \n\t  ", b""))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await client.json(["api", "graphql"])

    assert result is None


@pytest.mark.asyncio
async def test_graphql_builds_correct_args():
    """Test that graphql() builds correct command args with query and variables."""
    client = GhClient()
    query = "query { viewer { login } }"
    variables = {"owner": "acme", "number": 42}
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b'{"data": {}}', b""))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        await client.graphql(query, variables)

    mock_exec.assert_called_once()
    call_args = mock_exec.call_args[0]
    assert call_args[0] == "gh"
    assert call_args[1] == "api"
    assert call_args[2] == "graphql"
    assert "-f" in call_args
    assert f"query={query}" in call_args
    # Variables use -F (typed) flags; strings as-is, non-strings JSON-encoded
    assert "-F" in call_args
    assert "owner=acme" in call_args  # string passed as-is
    assert "number=42" in call_args  # int JSON-encoded to "42"


@pytest.mark.asyncio
async def test_graphql_encodes_non_string_variables():
    """Test that graphql() JSON-encodes booleans and None for -F flags."""
    client = GhClient()
    query = "query { test }"
    variables = {"flag": True, "val": None, "count": 5}
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b'{"data": {}}', b""))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        await client.graphql(query, variables)

    call_args = mock_exec.call_args[0]
    assert "flag=true" in call_args  # Python True → "true"
    assert "val=null" in call_args  # Python None → "null"
    assert "count=5" in call_args  # int → "5"


@pytest.mark.asyncio
async def test_graphql_without_variables():
    """Test that graphql() works without variables."""
    client = GhClient()
    query = "query { viewer { login } }"
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b'{"data": {}}', b""))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        await client.graphql(query)

    call_args = mock_exec.call_args[0]
    assert "-f" in call_args
    assert f"query={query}" in call_args
    # Should not have any variable flags
    assert all(not arg.startswith("var") for arg in call_args)


@pytest.mark.asyncio
async def test_graphql_raw():
    """Test that graphql_raw() passes args through to json()."""
    client = GhClient()
    args = ["api", "graphql", "-F", "query=test"]
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b'{"data": {}}', b""))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        result = await client.graphql_raw(args)

    mock_exec.assert_called_once()
    call_args = mock_exec.call_args[0]
    assert call_args[0] == "gh"
    assert call_args[1:] == tuple(args)
    assert result == {"data": {}}


@pytest.mark.asyncio
async def test_check_auth_success():
    """Test that check_auth() passes when auth status succeeds."""
    client = GhClient()
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"authenticated", b""))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        # Should not raise
        await client.check_auth()


@pytest.mark.asyncio
async def test_check_auth_raises_on_failure():
    """Test that check_auth() raises AuthenticationError on failure."""
    client = GhClient()
    mock_proc = AsyncMock()
    mock_proc.returncode = 1
    mock_proc.communicate = AsyncMock(return_value=(b"", b"not authenticated"))

    with (
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        pytest.raises(AuthenticationError, match="GitHub authentication failed"),
    ):
        await client.check_auth()


@pytest.mark.asyncio
async def test_run_with_empty_stdout_stderr():
    """Test that run() handles empty stdout/stderr correctly."""
    client = GhClient()
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(None, None))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await client.run(["repo", "view"])

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.mark.asyncio
async def test_run_raises_on_none_returncode():
    """Test that run() raises ProviderError when returncode is None (interrupted)."""
    client = GhClient()
    mock_proc = AsyncMock()
    mock_proc.returncode = None
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))

    with (
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        pytest.raises(ProviderError, match="gh command did not terminate"),
    ):
        await client.run(["repo", "view"])
