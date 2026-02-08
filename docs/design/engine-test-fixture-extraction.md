# Engine Test Fixture Extraction (Design Spec)

## Problem Statement

`tests/sync/test_engine.py` contains **13 identical copies** of this 8-line
`SyncConfig` construction:

```python
epics_path, stories_path, tasks_path = plan_json_files
config = SyncConfig(
    repo="owner/repo",
    project_url="https://github.com/orgs/org/projects/1",
    epics_path=epics_path,
    stories_path=stories_path,
    tasks_path=tasks_path,
    sync_path=sample_config.sync_path,
)
```

This duplication:

1. **Inflates the test file by ~100 lines** of boilerplate.
2. **Makes changes fragile.** Renaming a `SyncConfig` field requires touching
   all 13 call sites.
3. **Obscures test intent.** Readers must mentally skip the config block to find
   the actual test logic.

## Proposed Solution

### 1. Add a `config_for_engine` fixture to `tests/conftest.py`

```python
@pytest.fixture
def config_for_engine(
    plan_json_files: tuple[Path, Path, Path],
    tmp_path: Path,
) -> SyncConfig:
    """SyncConfig wired to generated plan JSON files (for engine tests)."""
    epics_path, stories_path, tasks_path = plan_json_files
    return SyncConfig(
        repo="owner/repo",
        project_url="https://github.com/orgs/org/projects/1",
        epics_path=epics_path,
        stories_path=stories_path,
        tasks_path=tasks_path,
        sync_path=tmp_path / "sync.json",
    )
```

### 2. Update all 13 test function signatures

Replace:

```python
async def test_xxx(mock_provider, mock_renderer, plan_json_files, sample_config):
    epics_path, stories_path, tasks_path = plan_json_files
    config = SyncConfig(
        repo="owner/repo",
        project_url="https://github.com/orgs/org/projects/1",
        epics_path=epics_path,
        stories_path=stories_path,
        tasks_path=tasks_path,
        sync_path=sample_config.sync_path,
    )
    engine = SyncEngine(mock_provider, mock_renderer, config)
```

With:

```python
async def test_xxx(mock_provider, mock_renderer, config_for_engine):
    engine = SyncEngine(mock_provider, mock_renderer, config_for_engine)
```

### 3. Handle tests that override config fields

Two tests use `dry_run=True`. For these, add a second fixture or use
`config_for_engine.model_copy(update={"dry_run": True})`:

```python
async def test_sync_dry_run_skips_writes(mock_provider, mock_renderer, config_for_engine):
    config = config_for_engine.model_copy(update={"dry_run": True})
    engine = SyncEngine(mock_provider, mock_renderer, config)
```

## Implementation Scope

- Modified files: `tests/conftest.py` (add 1 fixture), `tests/sync/test_engine.py`
  (remove ~100 lines of boilerplate, update 13 function signatures).
- No production code changes.

## Risks

- **Signature churn**: All 13 test functions change parameter lists. Must be done
  atomically in a single commit to keep the test suite green.
- **Fixture ordering**: `config_for_engine` depends on `plan_json_files` which
  depends on `tmp_path`. Pytest handles this automatically but worth verifying.

## Success Criteria

- All 13 tests pass with the new fixture.
- `test_engine.py` is ~100 lines shorter.
- No `SyncConfig(` constructor call remains in test function bodies (only in
  fixtures).
