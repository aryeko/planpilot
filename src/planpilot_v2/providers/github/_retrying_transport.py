"""httpx async transport wrapper with retry, backoff, and rate-limit handling."""

from __future__ import annotations

import asyncio
import logging
import random
import time

import httpx

_LOG = logging.getLogger(__name__)

# Status codes considered transient and eligible for automatic retry.
_RETRYABLE_STATUS_CODES = frozenset({429, 502, 503, 504})


class RetryingTransport(httpx.AsyncBaseTransport):
    """Wraps an httpx async transport with automatic retry on transient failures.

    Features:
    - Retry with exponential backoff + jitter (up to *max_retries* attempts)
    - Rate-limit pause on HTTP 429 (reads ``Retry-After`` header,
      blocks **all** concurrent requests via a shared event)
    - Retry on 502 / 503 / 504 server errors
    - Retry on transport-level errors (connection reset, timeout, etc.)
    """

    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        max_retries: int = 3,
    ) -> None:
        self._transport = transport or httpx.AsyncHTTPTransport()
        self._max_retries = max_retries

        self._rate_limit_lock = asyncio.Lock()
        self._rate_limit_clear = asyncio.Event()
        self._rate_limit_clear.set()
        self._rate_limit_pause_until = 0.0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        for attempt in range(self._max_retries + 1):
            await self._rate_limit_clear.wait()

            try:
                response = await self._transport.handle_async_request(request)
            except httpx.TransportError:
                if attempt >= self._max_retries:
                    raise
                await self._sleep_backoff(attempt)
                continue

            if response.status_code == 429:
                retry_after = self._parse_retry_after(response)
                await self._apply_rate_limit_pause(retry_after)
                if attempt < self._max_retries:
                    await self._sleep_backoff(attempt)
                    continue
                return response

            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < self._max_retries:
                retry_after = self._parse_retry_after(response)
                if retry_after > 0:
                    await asyncio.sleep(retry_after)
                await self._sleep_backoff(attempt)
                continue

            return response

        raise httpx.TransportError("Request failed after retries")  # pragma: no cover

    async def aclose(self) -> None:
        await self._transport.aclose()

    # ------------------------------------------------------------------
    # Rate-limit helpers
    # ------------------------------------------------------------------

    async def _apply_rate_limit_pause(self, retry_after: float) -> None:
        now = time.monotonic()
        async with self._rate_limit_lock:
            until = now + max(0.0, retry_after)
            if until <= self._rate_limit_pause_until:
                return
            self._rate_limit_pause_until = until
            self._rate_limit_clear.clear()

        await asyncio.sleep(max(0.0, self._rate_limit_pause_until - time.monotonic()))

        async with self._rate_limit_lock:
            if time.monotonic() >= self._rate_limit_pause_until:
                self._rate_limit_clear.set()

    @staticmethod
    def _parse_retry_after(response: httpx.Response) -> float:
        raw = response.headers.get("Retry-After")
        if raw is None:
            return 1.0
        try:
            return max(0.0, float(raw))
        except ValueError:
            return 1.0

    @staticmethod
    async def _sleep_backoff(attempt: int) -> None:
        seconds = min(4.0, float(2**attempt)) + random.uniform(0.0, 0.25)
        _LOG.warning("Retrying GitHub request (attempt %d)", attempt + 1)
        await asyncio.sleep(seconds)
