# Retry Strategy and Rate-Limiting (Design Spec)

## Problem Statement

The `planpilot` sync engine currently makes GitHub API calls without any retry mechanism or rate-limit awareness:

1. **No retries on transient failures**: Network timeouts, temporary API unavailability (5xx), or rate-limit hits (429) cause the entire sync to fail immediately.
2. **No rate-limit handling**: The engine doesn't parse the GitHub API `X-RateLimit-*` headers to proactively back off or schedule retries.
3. **Single-threaded execution**: Even though the engine uses `asyncio`, it processes issues sequentially, missing an opportunity to parallelize and reduce total wall-clock time.

For large plans (100+ issues), a single transient failure can cause the sync to fail and require manual re-run, reducing reliability and user experience.

## Proposed Solution

### 1. Exponential Backoff with Jitter

Implement retry logic in the `GhClient` layer (the async wrapper around the `gh` CLI):

- **Max retries**: Configurable, default 3.
- **Base delay**: 1 second (configurable).
- **Backoff strategy**: exponential with jitter.
  ```
  delay = base_delay * (2 ^ retry_count) + random(0, 1)
  ```
- **Retryable errors**: 
  - `5xx` HTTP status codes (server errors).
  - `429` (rate limit exceeded).
  - Network timeouts / connection errors (subprocess exits with specific codes).

### 2. Rate-Limit Awareness

Parse GitHub API response headers and adjust behavior:

- **`X-RateLimit-Remaining`**: Track remaining calls in quota.
- **`X-RateLimit-Reset`**: Timestamp when quota resets (Unix epoch).
- **`Retry-After`**: If present, use this value instead of exponential backoff.
- **Proactive throttling**: If remaining calls are low (e.g., < 10), sleep until reset time before making next call.

### 3. Implementation Scope

**Layer**: `GhClient.run()` and `GhClient.graphql()` methods.

- No changes to `SyncEngine`, `Provider`, or `BodyRenderer` interfaces.
- Retry logic is transparent to callers.
- Configuration options passed as init args to `GhClient`:
  ```python
  GhClient(
      max_retries=3,
      base_delay=1.0,
      min_remaining_threshold=10,  # Proactive throttle if < 10 calls left
  )
  ```

### 4. Logging

- **Debug**: Log each retry attempt with the delay and attempt count.
- **Info**: Log if rate-limit proactive throttling is triggered.
- **Warning**: Log if max retries exhausted (before final exception).

## Future Work

1. **Async parallelization**: Use `asyncio.gather()` in `SyncEngine` to create multiple issues concurrently (respecting rate limits).
2. **User-facing retry summary**: Include retry statistics in the final sync summary.
3. **Configurable retry policy**: Allow users to specify retry strategy (exponential vs. fixed backoff, max retries, etc.) via CLI args.

## Backward Compatibility

This change is **fully backward compatible**:

- Default behavior: 3 retries with sensible defaults.
- No API changes to `GhClient`, `Provider`, or `SyncEngine`.
- Existing error handling remains unchanged; retries happen silently within `GhClient`.

## Testing Strategy

1. **Unit tests**: Mock subprocess failures and verify retry logic.
2. **Integration tests** (future): Test against GitHub API with intentional rate-limit triggering.
3. **Manual testing**: Run sync on large plan during rate-limit window to verify behavior.

## Success Criteria

- Sync succeeds even after transient failures (up to max_retries).
- Rate-limit proactive throttling prevents 429 errors.
- Minimal performance impact (< 1% latency increase on success path).
- Comprehensive logging for debugging and monitoring.
