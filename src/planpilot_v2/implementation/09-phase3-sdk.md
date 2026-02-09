# Phase 3: SDK

**Layer:** L3 (SDK)
**Branch:** `v2/sdk`
**Phase:** 3 (after all Core modules merge into v2)
**Dependencies:** All Core modules + Contracts
**Design doc:** [`../docs/modules/sdk.md`](../docs/modules/sdk.md)

---

## Files to Create

| File | Contents |
|------|----------|
| `sdk.py` | `PlanPilot`, `load_config()`, `load_plan()` |
| `__init__.py` | Re-exports (public API surface) |

---

## PlanPilot Class

```python
class PlanPilot:
    def __init__(self, *, provider: Provider, renderer: BodyRenderer,
                 config: PlanPilotConfig) -> None:
        """Initialize with injected dependencies (advanced/testing)."""

    @classmethod
    async def from_config(cls, config: PlanPilotConfig, *,
                          renderer_name: str = "markdown") -> "PlanPilot":
        """Create PlanPilot from config.
        1. Resolve token via create_token_resolver(config)
        2. Build provider via create_provider(...)
        3. Build renderer via create_renderer(renderer_name)
        4. Return PlanPilot(provider, renderer, config)
        """

    async def sync(self, plan: Plan | None = None, *,
                   dry_run: bool = False) -> SyncResult:
        """Execute full sync pipeline.
        1. Load plan (if not provided)
        2. Validate plan
        3. Compute plan_id
        4. Enter provider (__aenter__)
        5. Construct + run SyncEngine
        6. Exit provider (__aexit__)
        7. Persist sync map to disk
        8. Return SyncResult
        """
```

---

## load_config()

```python
def load_config(path: str | Path) -> PlanPilotConfig:
    """Load config from JSON file.
    1. Resolve path to absolute
    2. Read JSON
    3. Parse via Pydantic
    4. Resolve relative paths against config file's parent
    5. Validate provider-specific invariants
    Raises: ConfigError
    """
```

---

## load_plan()

```python
def load_plan(*, unified: str | Path | None = None,
              epics: str | Path | None = None,
              stories: str | Path | None = None,
              tasks: str | Path | None = None) -> Plan:
    """Convenience wrapper. Raises: PlanLoadError"""
```

---

## Public API Re-exports (`__init__.py`)

| Category | Types |
|----------|-------|
| SDK | `PlanPilot`, `load_config`, `load_plan` |
| Config | `PlanPilotConfig`, `PlanPaths`, `FieldConfig` |
| Plan | `Plan`, `PlanItem`, `PlanItemType` |
| Sync | `SyncResult`, `SyncMap`, `SyncEntry` |
| Contracts | `Provider`, `BodyRenderer`, `RenderContext` |
| Factories | `create_provider`, `create_renderer`, `create_token_resolver` |
| Exceptions | `PlanPilotError`, `ConfigError`, `PlanLoadError`, `PlanValidationError`, `ProviderError`, `AuthenticationError`, `SyncError` |

---

## Test Strategy

| Test File | Key Cases |
|-----------|-----------|
| `test_sdk.py` | `from_config` wires dependencies, `sync` happy path with FakeProvider, `sync` loads plan from config when not provided, `sync` persists sync map, dry-run persists to .dry-run, error propagation (PlanLoadError, PlanValidationError, ProviderError), provider `__aexit__` called even on error, `load_config` reads JSON + resolves paths, `load_config` invalid JSON -> ConfigError |
