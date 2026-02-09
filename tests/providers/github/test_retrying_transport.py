"""Tests for RetryingTransport - retry, backoff, and rate-limit handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from planpilot.providers.github._retrying_transport import RetryingTransport

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(status_code: int = 200, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status_code=status_code, headers=headers or {})


def _make_request() -> httpx.Request:
    return httpx.Request("POST", "https://api.github.com/graphql")


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_defaults(self) -> None:
        transport = RetryingTransport()
        assert transport._max_retries == 3

    def test_custom_inner_transport(self) -> None:
        inner = AsyncMock(spec=httpx.AsyncBaseTransport)
        transport = RetryingTransport(transport=inner, max_retries=5)
        assert transport._transport is inner
        assert transport._max_retries == 5


# ---------------------------------------------------------------------------
# Successful requests
# ---------------------------------------------------------------------------


class TestSuccessfulRequests:
    @pytest.mark.asyncio
    async def test_returns_successful_response(self) -> None:
        inner = AsyncMock(spec=httpx.AsyncBaseTransport)
        inner.handle_async_request.return_value = _make_response(200)

        transport = RetryingTransport(transport=inner)
        response = await transport.handle_async_request(_make_request())

        assert response.status_code == 200
        assert inner.handle_async_request.call_count == 1


# ---------------------------------------------------------------------------
# Transport errors
# ---------------------------------------------------------------------------


class TestTransportErrors:
    @pytest.mark.asyncio
    @patch("planpilot.providers.github._retrying_transport.RetryingTransport._sleep_backoff", new_callable=AsyncMock)
    async def test_retries_on_transport_error_then_succeeds(self, mock_backoff: AsyncMock) -> None:
        inner = AsyncMock(spec=httpx.AsyncBaseTransport)
        inner.handle_async_request.side_effect = [
            httpx.TransportError("connection reset"),
            _make_response(200),
        ]

        transport = RetryingTransport(transport=inner, max_retries=2)
        response = await transport.handle_async_request(_make_request())

        assert response.status_code == 200
        assert inner.handle_async_request.call_count == 2
        mock_backoff.assert_awaited_once_with(0)

    @pytest.mark.asyncio
    @patch("planpilot.providers.github._retrying_transport.RetryingTransport._sleep_backoff", new_callable=AsyncMock)
    async def test_raises_after_max_retries_exhausted(self, mock_backoff: AsyncMock) -> None:
        inner = AsyncMock(spec=httpx.AsyncBaseTransport)
        inner.handle_async_request.side_effect = httpx.TransportError("fail")

        transport = RetryingTransport(transport=inner, max_retries=2)
        with pytest.raises(httpx.TransportError, match="fail"):
            await transport.handle_async_request(_make_request())

        assert inner.handle_async_request.call_count == 3  # initial + 2 retries
        assert mock_backoff.await_count == 2


# ---------------------------------------------------------------------------
# Rate-limit (429)
# ---------------------------------------------------------------------------


class TestRateLimit:
    @pytest.mark.asyncio
    @patch(
        "planpilot.providers.github._retrying_transport.RetryingTransport._sleep_backoff",
        new_callable=AsyncMock,
    )
    @patch(
        "planpilot.providers.github._retrying_transport.RetryingTransport._apply_rate_limit_pause",
        new_callable=AsyncMock,
    )
    async def test_429_retries_with_rate_limit_pause(self, mock_pause: AsyncMock, mock_backoff: AsyncMock) -> None:
        inner = AsyncMock(spec=httpx.AsyncBaseTransport)
        inner.handle_async_request.side_effect = [
            _make_response(429, {"Retry-After": "2"}),
            _make_response(200),
        ]

        transport = RetryingTransport(transport=inner, max_retries=2)
        response = await transport.handle_async_request(_make_request())

        assert response.status_code == 200
        mock_pause.assert_awaited_once()
        mock_backoff.assert_awaited_once_with(0)

    @pytest.mark.asyncio
    @patch(
        "planpilot.providers.github._retrying_transport.RetryingTransport._sleep_backoff",
        new_callable=AsyncMock,
    )
    @patch(
        "planpilot.providers.github._retrying_transport.RetryingTransport._apply_rate_limit_pause",
        new_callable=AsyncMock,
    )
    async def test_429_returns_response_when_retries_exhausted(
        self, mock_pause: AsyncMock, mock_backoff: AsyncMock
    ) -> None:
        inner = AsyncMock(spec=httpx.AsyncBaseTransport)
        inner.handle_async_request.return_value = _make_response(429)

        transport = RetryingTransport(transport=inner, max_retries=1)
        response = await transport.handle_async_request(_make_request())

        assert response.status_code == 429
        assert inner.handle_async_request.call_count == 2  # initial + 1 retry


# ---------------------------------------------------------------------------
# Server errors (502, 503, 504)
# ---------------------------------------------------------------------------


class TestServerErrors:
    @pytest.mark.asyncio
    @patch("planpilot.providers.github._retrying_transport.RetryingTransport._sleep_backoff", new_callable=AsyncMock)
    async def test_502_retries_then_succeeds(self, mock_backoff: AsyncMock) -> None:
        inner = AsyncMock(spec=httpx.AsyncBaseTransport)
        inner.handle_async_request.side_effect = [
            _make_response(502),
            _make_response(200),
        ]

        transport = RetryingTransport(transport=inner, max_retries=2)
        response = await transport.handle_async_request(_make_request())

        assert response.status_code == 200
        assert inner.handle_async_request.call_count == 2

    @pytest.mark.asyncio
    @patch("planpilot.providers.github._retrying_transport.RetryingTransport._sleep_backoff", new_callable=AsyncMock)
    async def test_server_error_returns_last_response_when_retries_exhausted(self, mock_backoff: AsyncMock) -> None:
        inner = AsyncMock(spec=httpx.AsyncBaseTransport)
        inner.handle_async_request.return_value = _make_response(503)

        transport = RetryingTransport(transport=inner, max_retries=1)
        response = await transport.handle_async_request(_make_request())

        assert response.status_code == 503
        assert inner.handle_async_request.call_count == 2

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("planpilot.providers.github._retrying_transport.RetryingTransport._sleep_backoff", new_callable=AsyncMock)
    async def test_server_error_respects_retry_after_header(
        self, mock_backoff: AsyncMock, mock_sleep: AsyncMock
    ) -> None:
        inner = AsyncMock(spec=httpx.AsyncBaseTransport)
        inner.handle_async_request.side_effect = [
            _make_response(503, {"Retry-After": "3"}),
            _make_response(200),
        ]

        transport = RetryingTransport(transport=inner, max_retries=2)
        response = await transport.handle_async_request(_make_request())

        assert response.status_code == 200
        mock_sleep.assert_awaited_once_with(3.0)


# ---------------------------------------------------------------------------
# _parse_retry_after
# ---------------------------------------------------------------------------


class TestParseRetryAfter:
    def test_returns_header_value_as_float(self) -> None:
        resp = _make_response(429, {"Retry-After": "5"})
        assert RetryingTransport._parse_retry_after(resp) == 5.0

    def test_returns_default_when_header_missing(self) -> None:
        resp = _make_response(429)
        assert RetryingTransport._parse_retry_after(resp) == 1.0

    def test_returns_default_for_non_numeric_header(self) -> None:
        resp = _make_response(429, {"Retry-After": "not-a-number"})
        assert RetryingTransport._parse_retry_after(resp) == 1.0

    def test_clamps_negative_values_to_zero(self) -> None:
        resp = _make_response(429, {"Retry-After": "-5"})
        assert RetryingTransport._parse_retry_after(resp) == 0.0


# ---------------------------------------------------------------------------
# _sleep_backoff
# ---------------------------------------------------------------------------


class TestSleepBackoff:
    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("random.uniform", return_value=0.1)
    async def test_backoff_increases_with_attempt(self, mock_uniform: AsyncMock, mock_sleep: AsyncMock) -> None:
        await RetryingTransport._sleep_backoff(0)
        mock_sleep.assert_awaited_with(1.1)  # 2^0 + 0.1

        await RetryingTransport._sleep_backoff(1)
        mock_sleep.assert_awaited_with(2.1)  # 2^1 + 0.1

        await RetryingTransport._sleep_backoff(2)
        mock_sleep.assert_awaited_with(4.1)  # min(4, 2^2) + 0.1

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("random.uniform", return_value=0.1)
    async def test_backoff_caps_at_4_seconds(self, mock_uniform: AsyncMock, mock_sleep: AsyncMock) -> None:
        await RetryingTransport._sleep_backoff(10)
        mock_sleep.assert_awaited_with(4.1)  # min(4, 2^10) + 0.1


# ---------------------------------------------------------------------------
# _apply_rate_limit_pause
# ---------------------------------------------------------------------------


class TestApplyRateLimitPause:
    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_sets_and_clears_rate_limit_event(self, mock_sleep: AsyncMock) -> None:
        transport = RetryingTransport(max_retries=1)

        assert transport._rate_limit_clear.is_set()
        await transport._apply_rate_limit_pause(0.0)
        assert transport._rate_limit_clear.is_set()

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_skips_when_existing_pause_is_later(self, mock_sleep: AsyncMock) -> None:
        transport = RetryingTransport(max_retries=1)
        # Set a far-future pause
        transport._rate_limit_pause_until = 1e15

        await transport._apply_rate_limit_pause(1.0)
        # Should return early without clearing
        assert transport._rate_limit_pause_until == 1e15


# ---------------------------------------------------------------------------
# aclose
# ---------------------------------------------------------------------------


class TestAclose:
    @pytest.mark.asyncio
    async def test_delegates_to_inner_transport(self) -> None:
        inner = AsyncMock(spec=httpx.AsyncBaseTransport)
        transport = RetryingTransport(transport=inner)

        await transport.aclose()
        inner.aclose.assert_awaited_once()
