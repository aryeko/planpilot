# Async Parallelization (Design Spec)

## Problem Statement

The `SyncEngine` uses `asyncio` throughout but executes all API calls
**sequentially**:

```python
# Phase 3: Upsert (current — sequential)
for epic in plan.epics:
    entry = await self._upsert_epic(epic, ...)
    sync_map.epics[epic.id] = entry

for story in plan.stories:
    entry = await self._upsert_story(story, ...)
    sync_map.stories[story.id] = entry

for task in plan.tasks:
    entry = await self._upsert_task(task, ...)
    sync_map.tasks[task.id] = entry
```

Each `_upsert_*` call creates an issue, optionally sets the type, adds to
project, and sets project fields — 3-5 sequential API calls per entity. For a
plan with 5 epics, 20 stories, and 80 tasks, that's 300+ sequential HTTP
round-trips at ~200ms each = **~60 seconds** of wall-clock time that could
be reduced to ~10-15 seconds with bounded concurrency.

The same pattern applies to phases 4 (body enrichment) and 5 (relation
setting).

## Proposed Solution

### 1. Bounded Semaphore for Concurrency Control

Use `asyncio.Semaphore` to limit concurrent API calls, respecting both GitHub
rate limits and API stability:

```python
class SyncEngine:
    def __init__(self, provider, renderer, config):
        ...
        self._semaphore = asyncio.Semaphore(config.max_concurrency or 5)
```

### 2. Parallel Upsert Within Phases

**Phase 3 — Upsert:**

Epics have no dependencies on each other, so they can be created in parallel.
Stories depend on their parent epic (for issue number references), so they must
wait until their epic is created. Tasks depend on their parent story.

```python
# Phase 3a: Epics (fully parallel)
epic_tasks = [self._upsert_epic(epic, ...) for epic in plan.epics]
epic_entries = await asyncio.gather(*epic_tasks)
for epic, entry in zip(plan.epics, epic_entries):
    sync_map.epics[epic.id] = entry

# Phase 3b: Stories (parallel, but each needs its epic to exist already)
story_tasks = [self._upsert_story(story, ...) for story in plan.stories]
story_entries = await asyncio.gather(*story_tasks)
for story, entry in zip(plan.stories, story_entries):
    sync_map.stories[story.id] = entry

# Phase 3c: Tasks (parallel, but each needs its story to exist already)
task_tasks = [self._upsert_task(task, ...) for task in plan.tasks]
task_entries = await asyncio.gather(*task_tasks)
for task, entry in zip(plan.tasks, task_entries):
    sync_map.tasks[task.id] = entry
```

**Phase 4 — Enrichment:**

All body updates are independent (each updates a different issue):

```python
update_coros = []
for task in plan.tasks:
    update_coros.append(self._enrich_task(task, plan_id, sync_map))
for story in plan.stories:
    update_coros.append(self._enrich_story(story, plan_id, sync_map))
for epic in plan.epics:
    update_coros.append(self._enrich_epic(epic, plan_id, sync_map))
await asyncio.gather(*update_coros)
```

**Phase 5 — Relations:**

Similarly parallelizable since each `add_blocked_by` / `add_sub_issue` call
targets a different pair of issues.

### 3. Semaphore-Wrapped API Calls

Wrap each provider call in the semaphore to avoid overwhelming the API:

```python
async def _guarded_create_issue(self, input: CreateIssueInput) -> IssueRef:
    async with self._semaphore:
        return await self._provider.create_issue(input)
```

Or apply the semaphore at the `GhClient` level (preferred — transparent to
engine):

```python
class GhClient:
    def __init__(self, max_concurrency: int = 5):
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def run(self, args, *, check=True):
        async with self._semaphore:
            # existing implementation
```

### 4. Configuration

Add `max_concurrency` to `SyncConfig`:

```python
class SyncConfig(BaseModel):
    ...
    max_concurrency: int = 5   # Max parallel API calls
```

Expose via CLI:

```text
--max-concurrency  Maximum parallel API calls (default: 5)
```

### 5. Error Handling with `gather`

Use `return_exceptions=True` to collect all errors, then report them together:

```python
results = await asyncio.gather(*coros, return_exceptions=True)
errors = [r for r in results if isinstance(r, Exception)]
if errors:
    raise SyncError(f"Failed to create {len(errors)} issue(s): {errors[0]}")
```

Or fail fast with the default behavior (`return_exceptions=False`) which
cancels remaining tasks on the first failure.

## Dependencies

- **Retry strategy** (see `retry-strategy.md`): Retries should be implemented
  first so that transient failures under concurrent load are handled gracefully.
- **Rate-limit awareness**: Concurrent calls make rate limiting more critical.

## Risks

- **Ordering sensitivity**: Stories depend on epic issue numbers being available.
  The phased approach (epics first, then stories, then tasks) preserves this
  constraint.
- **Rate-limit spikes**: 5 concurrent calls could hit secondary rate limits.
  Mitigated by the semaphore and the retry/rate-limit layer.
- **Error recovery**: If one issue creation fails mid-batch, the sync map may be
  partially populated. The idempotent re-run mechanism handles this (existing
  issues are detected on next sync).

## Implementation Scope

- Modified files: `src/planpilot/sync/engine.py` (refactor upsert loops,
  enrichment, and relations to use `asyncio.gather`).
- Modified files: `src/planpilot/config.py` (add `max_concurrency`).
- Modified files: `src/planpilot/cli.py` (add `--max-concurrency` arg).
- Optionally: `src/planpilot/providers/github/client.py` (add semaphore).

## Backward Compatibility

Fully backward compatible. Default `max_concurrency=5` changes behavior (faster)
but not correctness. Setting `max_concurrency=1` restores sequential behavior.

## Success Criteria

- Sync of a 100-entity plan completes in < 30s (vs ~60s sequential).
- All existing tests pass unchanged.
- New benchmark test compares sequential vs parallel timing.
- No increase in rate-limit errors (verified via retry-count metrics).

## Phased Rollout

1. **Phase A**: Add semaphore to `GhClient` only (controls concurrency without
   changing engine structure). Low risk.
2. **Phase B**: Parallelize Phase 3 upserts (epics, stories, tasks in batches).
3. **Phase C**: Parallelize Phase 4 enrichment and Phase 5 relations.
