# SDK Module Spec

The SDK module (`sdk.py`) is PlanPilot's public API surface and **composition root** — the only place that sees all Core modules and wires them together. External callers (CLI, scripts, CI integrations) interact exclusively through the SDK.

The SDK contains no business logic — pure orchestration and wiring.

**SDK (L3)** — depends on Core and Contracts (see [contracts.md](../design/contracts.md) for type definitions).

## PlanPilot Class

```python
class PlanPilot:
    """PlanPilot SDK — the public API for programmatic plan syncing."""

    def __init__(self, *, provider: Provider | None, renderer: BodyRenderer,
                 config: PlanPilotConfig) -> None:
        """Initialize with injected dependencies (advanced/testing)."""

    @classmethod
    async def from_config(cls, config: PlanPilotConfig, *,
                          renderer_name: str = "markdown") -> PlanPilot:
        """Create PlanPilot from config (recommended).

        1. Build renderer via create_renderer(renderer_name)
        2. Defer provider/auth construction to sync() mode branch
        3. Return PlanPilot(provider=None, renderer, config)
        """

    async def sync(self, plan: Plan | None = None, *,
                   dry_run: bool = False) -> SyncResult:
        """Execute the full sync pipeline.

        Raises:
            PlanLoadError, PlanValidationError, ProviderError, SyncError
        """
```

### `sync()` Lifecycle

```mermaid
flowchart TB
    Start["sync(plan=None, dry_run=False)"] --> LoadPlan{"plan provided?"}
    LoadPlan -- No --> Load["PlanLoader.load(config.plan_paths)"]
    LoadPlan -- Yes --> Validate
    Load --> Validate["PlanValidator.validate(plan, mode=config.validation_mode)"]
    Validate --> Hash["PlanHasher.compute_plan_id(plan)"]
    Hash --> Mode{"dry_run?"}
    Mode -- Yes --> DryProv["provider = DryRunProvider(...)"]
    Mode -- No --> Auth["resolve token + create provider"]
    Auth --> Enter["provider.__aenter__()"]
    Enter --> Engine["SyncEngine(provider, renderer, config, dry_run)"]
    DryProv --> Engine
    Engine --> Run["engine.sync(plan, plan_id)"]
    Run --> Exit{"apply mode?"}
    Exit -- Yes --> ProviderExit["provider.__aexit__()"]
    Exit -- No --> Persist["persist sync map to config.sync_path (or .dry-run)"]
    ProviderExit --> Persist
    Persist --> Return["return SyncResult"]
```

1. **Load plan** (if not provided) — `PlanLoader().load(config.plan_paths)`
2. **Validate plan** — `PlanValidator().validate(plan, mode=config.validation_mode)`
3. **Compute plan ID** — `PlanHasher().compute_plan_id(plan)` -> 12-char hex hash
4. **Choose provider by mode**
   - `dry_run=True`: use `DryRunProvider` (no token, no network)
   - `dry_run=False`: resolve token + build configured provider
5. **Enter provider for apply mode** — `async with provider` manages auth + context resolution
6. **Construct + run engine** — `SyncEngine(provider, renderer, config, dry_run).sync(plan, plan_id)`
7. **Exit provider in apply mode** — `__aexit__` ensures cleanup even on error
8. **Persist sync map** — apply mode -> `config.sync_path`, dry-run -> `<sync_path>.dry-run`
9. **Return result**

**Provider lifecycle:** `sync()` manages provider construction and lifecycle internally. Callers never manage `async with`.

**Error handling:** In apply mode, if engine/provider raises, `__aexit__` is still called. Exception propagates after cleanup.

## load_config()

```python
def load_config(path: str | Path) -> PlanPilotConfig:
    """Load and validate a PlanPilot configuration from a JSON file.

    1. Resolve path to absolute
    2. Read JSON
    3. Parse via Pydantic
    4. Resolve all relative paths against config file's parent directory
    5. Validate provider-specific invariants (board_url, create-type strategy)
    6. Return validated config

    Raises:
        ConfigError: If loading or validation fails.
    """
```

## load_plan()

```python
def load_plan(*, unified: str | Path | None = None, epics: str | Path | None = None,
              stories: str | Path | None = None, tasks: str | Path | None = None) -> Plan:
    """Load a plan from explicit path inputs (convenience wrapper).

    Raises:
        PlanLoadError: If loading fails.
    """
```

## Scaffold Functions

Config scaffolding and environment detection helpers, defined in `scaffold.py` and re-exported via the public API.

### `detect_target() -> str | None`

Best-effort detection of `owner/repo` from the current git remote. Parses SSH and HTTPS formats. Returns `None` if not in a git repo, git is not installed, or the remote URL cannot be parsed.

### `detect_plan_paths(base: Path | None = None) -> PlanPaths | None`

Scans common directories (`.plans/`, `plans/`) for existing plan files. Returns a `PlanPaths` when a coherent set is found (all three split files or a unified file), or `None` otherwise.

### `scaffold_config(*, target, board_url, ...) -> dict`

Builds and validates a planpilot config dict. Accepts all config fields as keyword arguments with sensible defaults, validates through `PlanPilotConfig`, and returns a minimal JSON-serialisable dict with default-valued fields omitted. Raises `ConfigError` on validation failure.

### `write_config(config: dict, path: Path) -> None`

Writes a config dict to a JSON file, creating parent directories as needed.

### `create_plan_stubs(plan_paths: dict, *, base: Path | None = None) -> list[Path]`

Creates empty plan files for paths that don't already exist. Returns the list of created paths.

## Public API Surface (re-exports)

The SDK re-exports selected types so callers import from one place:

| Category | Types |
|----------|-------|
| **SDK** | `PlanPilot`, `load_config`, `load_plan` |
| **Scaffold** | `scaffold_config`, `detect_target`, `detect_plan_paths`, `write_config`, `create_plan_stubs` |
| **Config** | `PlanPilotConfig`, `PlanPaths`, `FieldConfig` |
| **Plan** | `Plan`, `PlanItem`, `PlanItemType` |
| **Sync** | `SyncResult`, `SyncMap`, `SyncEntry` |
| **Contracts** | `Provider`, `BodyRenderer`, `RenderContext` |
| **Factories** | `create_provider`, `create_renderer`, `create_token_resolver` |
| **Exceptions** | `PlanPilotError`, `ConfigError`, `PlanLoadError`, `PlanValidationError`, `ProviderError`, `AuthenticationError`, `SyncError` |

## Programmatic Usage

```python
from planpilot import PlanPilot, PlanItemType, load_config

config = load_config("planpilot.json")
pp = await PlanPilot.from_config(config, renderer_name="markdown")
result = await pp.sync(dry_run=False)

print(f"Created {result.items_created[PlanItemType.EPIC]} epics")
print(f"Sync map: {result.sync_map.model_dump_json()}")
```

### Scaffold Usage

```python
from planpilot import detect_target, detect_plan_paths, scaffold_config, write_config
from pathlib import Path

target = detect_target() or "owner/repo"
plan_paths = detect_plan_paths()

config = scaffold_config(
    target=target,
    board_url="https://github.com/orgs/myorg/projects/1",
)
write_config(config, Path("planpilot.json"))
```

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| `PlanPilot.from_config()` is the default entrypoint | SDK remains composition root |
| `__init__` accepts injected dependencies | Advanced/testing scenarios |
| `sync()` manages provider lifecycle | Simple API — no `async with` boilerplate |
| `plan` parameter optional on `sync()` | Config-driven and programmatic usage both supported |
| SDK persists sync map, not engine | Engine is pure orchestration (no I/O) |
| `load_config()` is standalone, not a method | Used before `PlanPilot` construction |

## File Structure

```text
src/planpilot/
├── __init__.py            # Re-exports
├── sdk.py                 # PlanPilot, load_config(), load_plan()
├── scaffold.py            # detect_target(), detect_plan_paths(), scaffold_config(), write_config(), create_plan_stubs()
```
