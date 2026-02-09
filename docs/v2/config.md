# Config Module Spec

## Overview

The config module provides configuration loading and validation for PlanPilot sync runs. It consists of two parts:

1. **Config domain (Contracts layer)** — Pure Pydantic data models: `PlanPilotConfig`, `PlanPaths`, `FieldConfig`
2. **Config loader (SDK layer)** — `load_config()` function that reads a JSON file and returns a validated `PlanPilotConfig`

The config domain has **no dependencies** on any other domain. It is a foundation alongside the plan domain.

## Dependencies

### Config domain (Contracts)

| Dependency | Types |
|-----------|-------|
| stdlib | `pathlib.Path` |
| third-party | `pydantic.BaseModel` |

No dependency on plan, item, sync, provider, or renderer domains.

### Config loader (SDK)

| Dependency | Types |
|-----------|-------|
| config domain | `PlanPilotConfig` |
| exceptions | `ConfigError` |

## Config Domain Models

### `FieldConfig`

Project field preferences. Controls which field values the provider sets on created items.

```python
class FieldConfig(BaseModel):
    """Project field preferences for created items.

    These are user-facing names/values. The provider resolves them
    to internal IDs during __aenter__.
    """

    status: str = "Backlog"
    """Status field value to set (e.g. "Backlog", "In Progress")."""

    priority: str = "P1"
    """Priority field value to set (e.g. "P1", "P2")."""

    iteration: str = "active"
    """Iteration to assign. "active" = current iteration, "none" = skip."""

    size_field: str = "Size"
    """Name of the size/estimate field on the project board."""

    size_from_tshirt: bool = True
    """Whether to map PlanItem.estimate.tshirt to the size field."""

    create_type_strategy: str = "issue-type"
    """Create type behavior: "issue-type" or "label".

    - issue-type: map EPIC/STORY/TASK to provider issue types
    - label: map EPIC/STORY/TASK to labels (e.g. type:epic)
    """

    create_type_map: dict[str, str] = {
        "EPIC": "Epic",
        "STORY": "Story",
        "TASK": "Task",
    }
    """Plan item type -> provider value mapping for create_type_strategy.

    For issue-type strategy, values are issue type names.
    For label strategy, values are label names.
    """
```

**Cross-provider field mapping:** These field names use GitHub Projects v2 terminology and are defaults, not guarantees. Providers interpret them in their own context and may require target-specific field names to exist:

| FieldConfig field | GitHub | Jira |
|-------------------|--------|------|
| `status` | Status column | Workflow status |
| `priority` | Priority field | Priority field |
| `iteration` | Iteration field | Sprint |
| `size_field` | Custom "Size" field | Story points field |
| `create_type_strategy` | Issue type or label strategy | Issue type or label strategy |
| `create_type_map` | EPIC/STORY/TASK -> issue type or label | EPIC/STORY/TASK -> issue type or label |

If a configured field does not exist in the provider target, provider setup must fail fast with a clear `ConfigError`/`ProviderError`.

### `PlanPaths`

Paths configuration for plan input files. Supports two mutually exclusive modes:

```python
class PlanPaths(BaseModel):
    """Paths to plan JSON files.

    Exactly one mode must be used:
    - Multi-file: set epics, stories, and/or tasks paths
    - Unified: set the unified path (single file with all items)
    """

    epics: Path | None = None
    """Path to epics JSON file (multi-file mode)."""

    stories: Path | None = None
    """Path to stories JSON file (multi-file mode)."""

    tasks: Path | None = None
    """Path to tasks JSON file (multi-file mode)."""

    unified: Path | None = None
    """Path to single combined plan file (unified mode)."""
```

**Validation rules (model validator):**

| Rule | Description |
|------|------------|
| Mutual exclusivity | If `unified` is set, none of `epics`/`stories`/`tasks` may be set |
| At least one path | At least one of the four fields must be non-None |
| Multi-file minimum | In multi-file mode, at least one of `epics`/`stories`/`tasks` must be set (partial plans are allowed — e.g. epics + stories without tasks) |

### `PlanPilotConfig`

Top-level configuration, loadable from a `planpilot.json` file.

```python
class PlanPilotConfig(BaseModel):
    """Top-level configuration for a PlanPilot sync run.

    Loadable from a JSON config file so the SDK and CLI share a
    single source of truth. All paths in the config are resolved
    relative to the config file's directory.
    """

    provider: str
    """Provider name (e.g. "github"). Must match a registered provider."""

    target: str
    """Target designation (e.g. "owner/repo" for GitHub)."""

    auth: str = "gh-cli"
    """Auth method. Provider-specific. For GitHub: "gh-cli" (default),
    "env" (reads GITHUB_TOKEN), or "token" (uses the token field)."""

    token: str | None = None
    """Static auth token. Only used when auth="token".
    Should not be committed to version control."""

    board_url: str
    """Project board URL.

    v2 launch is GitHub-first and requires a project URL. Repo-only
    sync without a board is out of scope for v2.
    """

    plan_paths: PlanPaths
    """Paths to plan JSON files."""

    validation_mode: str = "strict"
    """Plan validation mode: "strict" or "partial".

    - strict: unresolved parent/dependency references are errors
    - partial: unresolved refs are allowed when missing items are not loaded
    """

    sync_path: Path = Path("sync-map.json")
    """Path to write apply-mode sync map JSON.

    Dry-run writes to a sibling file with `.dry-run` suffix.
    Example: `sync-map.json.dry-run`.
    """

    label: str = "planpilot"
    """Label to apply to all created items."""

    field_config: FieldConfig = FieldConfig()
    """Project field preferences (status, priority, iteration, size, create-type strategy)."""

    model_config = {"frozen": True}
```

**Auth/token validation rules:**

| `auth` value | `token` value | Result |
|--------------|---------------|--------|
| `"gh-cli"` | `None` | Valid |
| `"env"` | `None` | Valid |
| `"token"` | non-empty string | Valid |
| `"token"` | `None` / empty | Invalid (`ConfigError`) |
| `"gh-cli"` or `"env"` | non-empty string | Invalid (`ConfigError`, prevents ambiguous secret source) |

**Launch scope note:** v2 launch targets the GitHub provider. Other providers may define additional `auth` values and env/token semantics in their provider docs.

**GitHub-specific config rules (v2 launch):**
- `board_url` is required and must be a GitHub Projects v2 URL.
- Owner type is resolved from URL shape:
  - `https://github.com/orgs/<org>/projects/<number>` -> organization-owned project
  - `https://github.com/users/<user>/projects/<number>` -> user-owned project
- For user-owned projects, `field_config.create_type_strategy` must be `label`.
- If configured strategy or relation features are unsupported by the target, provider setup fails with explicit errors.

**Design decisions:**

| Decision | Rationale |
|----------|-----------|
| `provider` is a string, not an enum | Open for extension — new providers added without modifying config models |
| `auth` is a string, not an enum | Same as `provider` — open for extension per provider |
| `board_url` required for GitHub launch | v2 scope excludes repo-only sync; project-driven workflows are canonical |
| `validation_mode` is persisted config | Partial plan workflows must be explicit and repeatable |
| No `dry_run` field | Dry-run is a per-invocation execution mode, not persisted config. Passed as a parameter to `PlanPilot.sync(dry_run=...)` by the CLI or SDK caller |
| No `verbose` field | Logging verbosity is a CLI concern, not a config concern. The SDK uses standard `logging` levels |
| `frozen = True` | Config is immutable after creation — prevents accidental mutation during sync |

## Path Resolution

All paths in `PlanPilotConfig` are relative to the config file's parent directory. The `load_config()` function resolves them to absolute paths during loading.

**Resolution rules:**

| Field | Resolution |
|-------|-----------|
| `plan_paths.epics` | Relative to config file directory |
| `plan_paths.stories` | Relative to config file directory |
| `plan_paths.tasks` | Relative to config file directory |
| `plan_paths.unified` | Relative to config file directory |
| `sync_path` | Relative to config file directory |
| Dry-run output path | Derived from `sync_path` + `.dry-run` suffix |

**Example:**

```
project/
├── planpilot.json        # {"plan_paths": {"epics": "plans/epics.json"}}
├── plans/
│   ├── epics.json
│   ├── stories.json
│   └── tasks.json
├── sync-map.json
└── sync-map.json.dry-run
```

When loaded via `load_config("project/planpilot.json")`, `plan_paths.epics` resolves to `project/plans/epics.json`.

CLI summaries should display the resolved absolute sync-map path for deterministic output.

## Config Loader

The `load_config()` function lives in the SDK layer (it performs file I/O and is a convenience for callers).

```python
def load_config(path: str | Path) -> PlanPilotConfig:
    """Load and validate a PlanPilot configuration from a JSON file.

    Args:
        path: Path to the config JSON file (e.g. "planpilot.json").

    Returns:
        Validated PlanPilotConfig with all paths resolved relative
        to the config file's parent directory.

    Raises:
        ConfigError: If the file is missing, unreadable, contains
            invalid JSON, or fails validation.
    """
```

**Behavior:**

1. Resolve `path` to absolute
2. Read the JSON file
3. Parse into `PlanPilotConfig` via Pydantic (schema validation happens here)
4. Resolve all relative paths in `plan_paths` and `sync_path` against the config file's parent directory
5. Validate provider-specific invariants (`board_url`, create-type strategy compatibility)
6. Return validated config

**Error handling:** All I/O and validation errors are wrapped in `ConfigError` (a new exception subclass of `PlanPilotError`).

### Runtime Parameters

Execution mode (`dry_run`) is **not** part of the persisted config. It is passed as a parameter to `PlanPilot.sync(dry_run=True)`. This keeps the config file as a stable, committable artifact that describes *what* to sync, while the caller decides *how* (preview vs apply) per invocation.

## JSON Schema

Example `planpilot.json`:

```json
{
  "provider": "github",
  "target": "owner/repo",
  "auth": "gh-cli",
  "board_url": "https://github.com/orgs/owner/projects/1",
  "plan_paths": {
    "epics": "plans/epics.json",
    "stories": "plans/stories.json",
    "tasks": "plans/tasks.json"
  },
  "validation_mode": "partial",
  "sync_path": "sync-map.json",
  "label": "planpilot",
  "field_config": {
    "status": "Backlog",
    "priority": "P1",
    "iteration": "active",
    "size_field": "Size",
    "size_from_tshirt": true,
    "create_type_strategy": "label",
    "create_type_map": {
      "EPIC": "type:epic",
      "STORY": "type:story",
      "TASK": "type:task"
    }
  }
}
```

Minimal config (uses defaults except required fields):

```json
{
  "provider": "github",
  "target": "owner/repo",
  "board_url": "https://github.com/orgs/owner/projects/1",
  "plan_paths": {
    "unified": "plan.json"
  }
}
```

## File Structure

```
src/planpilot/
├── contracts/
│   └── config.py          # PlanPilotConfig, PlanPaths, FieldConfig
├── sdk.py                 # load_config() lives here (or a dedicated config_loader.py)
└── exceptions.py          # ConfigError added to hierarchy
```

## Exception

```python
class ConfigError(PlanPilotError):
    """Raised when a config file cannot be loaded or validated."""
```

Added to the existing exception hierarchy in `exceptions.py`.

## Contracts Validation

The config module confirms these types are sufficient for all consumers:

| Consumer | Fields Used |
|----------|-----------|
| **SDK** (`PlanPilot`) | All fields — wires auth, provider, renderer, plan loading, validation mode, sync map persistence |
| **Engine** (`SyncEngine`) | `.target`, `.board_url`, `.label` (dry_run passed separately) |
| **Token resolver factory** | `.auth`, `.token` |
| **Provider factory** | `.provider`, `.target`, `.board_url`, `.label`, `.field_config` |
| **Plan validator** | `.validation_mode` |
| **Plan loader** | `.plan_paths` (all sub-fields) |
| **CLI** | Loads via `load_config()`, passes `dry_run` to `sync()` |

## Changes from v1

| v1 | v2 | Rationale |
|----|-----|-----------|
| `SyncConfig` built from CLI args only | `PlanPilotConfig` loadable from JSON file | SDK callers don't use CLI; config file is the single source of truth |
| Flat path fields (`epics_path`, `stories_path`, `tasks_path`) | Nested `PlanPaths` with multi-file and unified modes | Cleaner grouping, supports single-file plans |
| `repo` field (GitHub-specific) | `target` field (provider-agnostic) | Works for any provider (GitHub: "owner/repo", Jira: "project-key") |
| `project_url` field (GitHub-specific) | `board_url` field (provider-agnostic name, required for GitHub launch) | Generic naming plus explicit v2 launch scope |
| No auth config | `auth` field with resolver strategies | Separated auth from provider; configurable per-environment |
| No validation mode | `validation_mode` with `strict`/`partial` | Enables partial-plan workflows intentionally |
| `verbose` in config | Not in config | Logging is a CLI/runtime concern, not persisted config |
| `dry_run` in config | Not in config | Execution mode is per-invocation, not persisted |
| Mutable model | `frozen = True` | Prevents accidental mutation during sync pipeline |
| No path resolution | Paths resolved relative to config file | Config files work from any working directory |
| No `load_config()` | `load_config()` in SDK | File I/O in SDK, not in Contracts |
