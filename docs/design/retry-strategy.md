# Retry Strategy and Rate-Limiting (Design Spec)

## Problem Statement

The `planpilot` sync engine makes GitHub API calls via the `gh` CLI without any
retry mechanism or rate-limit awareness. A single transient failure (network
blip, 5xx, or rate-limit hit) aborts the entire sync, requiring manual re-run.

For a plan with 5 epics, 20 stories, and 80 tasks, there are 300+ API calls.
The probability that at least one fails transiently is non-trivial, especially
during CI or peak-hour GitHub load.

## Architecture Constraint

All API calls go through `GhClient`, which shells out to the `gh` CLI binary:

```text
SyncEngine -> Provider -> GhClient.run() -> subprocess("gh", ...) -> GitHub API
```

This means:

- **HTTP headers are not directly accessible.** The `gh` CLI consumes
  `X-RateLimit-*` and `Retry-After` headers internally but does not expose them
  to callers.
- **Errors surface as non-zero exit codes + stderr text.** The `gh` CLI
  writes messages like `HTTP 429`, `HTTP 502`, or
  `You have exceeded a secondary rate limit` to stderr.
- **GraphQL errors may arrive as HTTP 200** with `{"errors": [...]}` in the
  response body. The current `graphql()` method does not check for these at all.
- **The `gh` CLI has no built-in `--retry` flag** (feature request
  [cli/cli#7533](https://github.com/cli/cli/issues/7533) is still open).

Retry logic must therefore be implemented in Python, keying off exit codes and
stderr/stdout content.

## Proposed Solution

### 1. Retryable Error Detection

Classify errors into retryable and non-retryable:

**Retryable (transient):**

| Signal | Detection | Type |
|--------|-----------|------|
| Rate limit (primary) | stderr contains `HTTP 429` or `x-ratelimit-remaining` is `0` | Rate limit |
| Rate limit (secondary) | stderr contains `exceeded a secondary rate limit` | Rate limit |
| Server error | stderr contains `HTTP 502`, `HTTP 503`, or `HTTP 504` | Server |
| Connection error | stderr contains `connection refused`, `timeout`, `EOF` | Network |
| GraphQL rate-limit error | stdout JSON contains `{"errors": [{"type": "RATE_LIMITED"}]}` | Rate limit |

**Non-retryable (permanent):**

| Signal | Detection |
|--------|-----------|
| Authentication failure | stderr contains `HTTP 401` or exit from `check_auth` |
| Not found | stderr contains `HTTP 404` |
| Bad request / query error | stderr contains `HTTP 400`, `HTTP 422` |
| GraphQL validation error | stdout JSON `errors` without `RATE_LIMITED` type |

### 2. Retry Policy

```python
@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay: float = 1.0          # seconds
    max_delay: float = 60.0          # cap for backoff
    jitter: float = 1.0              # max random jitter in seconds
    rate_limit_buffer: float = 5.0   # extra seconds after rate-limit reset
```

**Backoff formula** (decorrelated jitter, per
[AWS architecture blog](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)):

```python
delay = min(max_delay, base_delay * (2 ** attempt)) + uniform(0, jitter)
```

For rate-limit errors specifically, if the `gh` stderr contains a timestamp or
`Retry-After`-style hint, parse and honor it. Otherwise fall back to the
exponential formula.

### 3. Implementation: `GhClient`

The retry wrapper goes into `GhClient.run()` — the single choke-point for all
`gh` subprocess calls. No changes to `Provider`, `SyncEngine`, or
`BodyRenderer`.

```python
class GhClient:
    def __init__(self, retry_policy: RetryPolicy | None = None) -> None:
        self._retry = retry_policy or RetryPolicy()

    async def run(self, args: list[str], *, check: bool = True) -> CompletedProcess:
        last_error: ProviderError | None = None

        for attempt in range(1 + self._retry.max_retries):
            result = await self._exec(args)

            if result.returncode == 0:
                # Check for GraphQL-level errors in successful HTTP responses
                if not self._has_retryable_graphql_error(result.stdout):
                    return result

            if not check:
                return result  # Caller opted out of error checking

            error = ProviderError(
                f"gh command failed: {' '.join(['gh', *args])}\n{result.stderr}"
            )

            if not self._is_retryable(result):
                raise error

            last_error = error
            delay = self._compute_delay(attempt, result.stderr)
            logger.warning(
                "Retryable error (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1, self._retry.max_retries + 1, delay,
                result.stderr.strip().split('\n')[0],
            )
            await asyncio.sleep(delay)

        raise last_error  # Max retries exhausted

    def _is_retryable(self, result: CompletedProcess) -> bool:
        """Check if the error is transient and worth retrying."""
        stderr = result.stderr.lower()
        retryable_patterns = [
            "http 429", "http 502", "http 503", "http 504",
            "secondary rate limit", "exceeded a secondary rate limit",
            "connection refused", "timeout", "eof",
        ]
        return any(p in stderr for p in retryable_patterns)

    def _has_retryable_graphql_error(self, stdout: str) -> bool:
        """Check for rate-limit errors in GraphQL JSON responses."""
        if not stdout.strip():
            return False
        try:
            data = json.loads(stdout)
            errors = data.get("errors", [])
            return any(e.get("type") == "RATE_LIMITED" for e in errors)
        except (json.JSONDecodeError, AttributeError):
            return False

    def _compute_delay(self, attempt: int, stderr: str) -> float:
        """Compute delay with exponential backoff and jitter."""
        base = min(
            self._retry.max_delay,
            self._retry.base_delay * (2 ** attempt),
        )
        jitter = uniform(0, self._retry.jitter)
        return base + jitter

    async def _exec(self, args: list[str]) -> CompletedProcess:
        """Raw subprocess execution (no retry logic)."""
        cmd = ["gh", *args]
        logger.debug("Running: %s", " ".join(cmd))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()
        return CompletedProcess(
            returncode=proc.returncode if proc.returncode is not None else 0,
            stdout=stdout_bytes.decode() if stdout_bytes else "",
            stderr=stderr_bytes.decode() if stderr_bytes else "",
        )
```

### 4. GraphQL Error Checking

A separate but related gap: `graphql()` currently ignores `{"errors": [...]}` in
successful (HTTP 200) responses. Add a check after parsing:

```python
async def graphql(self, query: str, variables: dict[str, Any] | None = None) -> Any:
    ...
    data = await self.json(args)
    if isinstance(data, dict) and "errors" in data:
        errors = data["errors"]
        messages = "; ".join(e.get("message", "unknown") for e in errors)
        raise ProviderError(f"GraphQL error: {messages}")
    return data
```

This pairs with the retry logic: if the error type is `RATE_LIMITED`, the retry
wrapper catches the `ProviderError` and retries.

### 5. Circuit Breaker (Optional)

If N consecutive calls fail (e.g., 10 in a row), stop retrying individual calls
and abort the sync early with a clear message. This prevents burning through
hundreds of entities when GitHub is down:

```python
class CircuitBreaker:
    def __init__(self, threshold: int = 10) -> None:
        self._consecutive_failures = 0
        self._threshold = threshold

    def record_success(self) -> None:
        self._consecutive_failures = 0

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._threshold:
            raise SyncError(
                f"Circuit breaker tripped: {self._threshold} consecutive "
                "API failures. Aborting sync."
            )
```

### 6. Configuration Surface

Pass retry settings through `SyncConfig` and expose via CLI:

```python
class SyncConfig(BaseModel):
    ...
    max_retries: int = 3
    retry_base_delay: float = 1.0
```

```text
--max-retries     Max retry attempts per API call (default: 3, 0 = disable)
```

### 7. Logging

| Level | When |
|-------|------|
| DEBUG | Every `gh` invocation (already exists) |
| WARNING | Each retry attempt (includes attempt number, delay, and first line of error) |
| WARNING | Circuit breaker approaching threshold (e.g., 7/10 consecutive failures) |
| ERROR | Max retries exhausted (final exception raised) |

## Implementation Scope

| File | Change |
|------|--------|
| `src/planpilot/providers/github/client.py` | Add `RetryPolicy`, refactor `run()` into `_exec()` + retry loop, add `_is_retryable()`, `_compute_delay()`, `_has_retryable_graphql_error()`. Add GraphQL error check to `graphql()`. |
| `src/planpilot/config.py` | Add `max_retries` and `retry_base_delay` fields to `SyncConfig`. |
| `src/planpilot/cli.py` | Add `--max-retries` argument. |
| `src/planpilot/exceptions.py` | No changes (existing `ProviderError` is sufficient). |
| `src/planpilot/providers/base.py` | No changes. |
| `src/planpilot/sync/engine.py` | No changes. |

## Testing Strategy

### Unit Tests (`tests/providers/github/test_client.py`)

| Test | Scenario |
|------|----------|
| `test_retry_on_502` | Subprocess returns exit 1 + "HTTP 502" twice, then succeeds. Verify 3 calls total. |
| `test_retry_on_429` | Subprocess returns "HTTP 429" then succeeds. Verify delay was applied. |
| `test_retry_on_secondary_rate_limit` | stderr contains "exceeded a secondary rate limit". Verify retry. |
| `test_no_retry_on_404` | Subprocess returns "HTTP 404". Verify immediate `ProviderError`, no retry. |
| `test_no_retry_on_401` | Auth error. Verify immediate raise, no retry. |
| `test_max_retries_exhausted` | All attempts fail with 502. Verify `ProviderError` raised after `max_retries + 1` attempts. |
| `test_retry_disabled` | `max_retries=0`. Verify single attempt, no retry. |
| `test_graphql_rate_limit_error` | HTTP 200 with `{"errors": [{"type": "RATE_LIMITED"}]}`. Verify retry. |
| `test_graphql_validation_error` | HTTP 200 with non-retryable `{"errors": [...]}`. Verify immediate raise. |
| `test_backoff_delay_increases` | Mock `asyncio.sleep` and verify delays grow exponentially. |
| `test_check_false_skips_retry` | `check=False` returns result even on failure, no retry. |

### Integration Tests (future, with FakeProvider)

Covered in `fake-provider-integration-tests.md`.

## Dependencies and Cross-References

- **Async parallelization** (`async-parallelization.md`): Concurrent calls make
  retry and rate-limit handling more critical. Implement retry first, then
  parallelization.
- **FakeProvider** (`fake-provider-integration-tests.md`): A FakeProvider that
  simulates transient failures would validate retry behavior end-to-end.

## Backward Compatibility

Fully backward compatible:

- Default: 3 retries with exponential backoff. Existing behavior on the
  success path is unchanged (zero overhead — no sleep, no extra checks).
- `--max-retries 0` restores the current fail-fast behavior.
- `GhClient()` with no arguments behaves identically to today (default
  `RetryPolicy`).

## Success Criteria

- Sync succeeds through transient 502/429 errors (up to `max_retries`).
- Non-retryable errors (401, 404, 422) fail immediately without delay.
- GraphQL-level errors are detected and either retried or raised.
- Backoff delays are logarithmic, not linear.
- `--max-retries 0` disables retry entirely.
- All 11 new unit tests pass. Existing tests unaffected.
