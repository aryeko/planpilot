# FakeProvider Integration Tests (Design Spec)

## Problem Statement

All `SyncEngine` tests currently use `AsyncMock(spec=Provider)` with manually
wired return values. This approach:

1. **Tests the engine against mocks, not against the `Provider` contract.** If a
   concrete provider changes its return shape, mock-based tests continue to pass
   while real runs break.
2. **Duplicates setup across tests.** Each test must configure 13+ mock
   attributes (check_auth, get_repo_context, create_issue, ...) to exercise a
   single code path.
3. **Cannot catch integration bugs** such as incorrect field types passed to
   `set_project_field`, or ordering issues between `add_to_project` and
   `set_project_field`.

## Proposed Solution

### 1. Create `FakeProvider`

Add `tests/fakes/fake_provider.py` (or `tests/conftest.py`) implementing the
full `Provider` ABC backed by in-memory data structures:

```python
class FakeProvider(Provider):
    """In-memory provider for integration testing."""

    def __init__(self) -> None:
        self.issues: dict[str, FakeIssue] = {}
        self.project_items: dict[str, dict[str, Any]] = {}
        self.relations: dict[str, set[str]] = {}   # blocked_by
        self.parents: dict[str, str | None] = {}    # sub-issue
        self._next_number = 1
        self._next_id = 1
```

Key behaviors:

- `create_issue` assigns an auto-incrementing number and node ID, stores the
  issue body and labels, returns an `IssueRef`.
- `search_issues` scans stored issues by plan markers in their bodies.
- `build_issue_map` delegates to `parse_markers` and builds the same nested dict
  the engine expects.
- `add_to_project`, `set_project_field` store values that can be asserted on.
- `add_sub_issue`, `add_blocked_by` record relations in dicts.
- `get_issue_relations` returns a `RelationMap` built from internal state.

### 2. Write Integration Tests

Create `tests/integration/test_engine_integration.py`:

| Test | What it validates |
|------|-------------------|
| `test_full_sync_creates_all_entities` | Epic, story, task issues created with correct bodies and markers |
| `test_full_sync_sets_relations` | Sub-issue and blocked-by relations match plan topology |
| `test_idempotent_resync` | Running sync twice on the same plan creates no duplicates |
| `test_partial_resync_skips_existing` | Pre-seed one epic; verify it's reused, others created |
| `test_cross_references_in_bodies` | After enrichment, task bodies contain `#<story_num>` refs |
| `test_project_fields_set_correctly` | Status, priority, iteration, size fields recorded on project items |

### 3. Shared Fixtures

```python
@pytest.fixture
def fake_provider() -> FakeProvider:
    return FakeProvider()

@pytest.fixture
def integration_engine(fake_provider, tmp_path):
    renderer = MarkdownRenderer()  # Use real renderer, not mock
    config = SyncConfig(
        repo="test/repo",
        project_url="https://github.com/orgs/test/projects/1",
        epics_path=tmp_path / "epics.json",
        stories_path=tmp_path / "stories.json",
        tasks_path=tmp_path / "tasks.json",
        sync_path=tmp_path / "sync.json",
    )
    return SyncEngine(fake_provider, renderer, config), fake_provider, config
```

## Implementation Scope

- New file: `tests/fakes/fake_provider.py` (~150 lines)
- New file: `tests/integration/test_engine_integration.py` (~200 lines)
- No changes to production code.

## Backward Compatibility

Test-only change. No impact on production behavior.

## Success Criteria

- FakeProvider passes a conformance test that checks every abstract method.
- Integration tests exercise the full 5-phase sync pipeline end-to-end.
- At least one idempotency test proves re-runs are safe.
- Coverage of `engine.py` increases by 5-10%.
