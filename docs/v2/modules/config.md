# Config Module Spec

The config module provides configuration models and loading for PlanPilot sync runs:

1. **Config domain (Contracts layer)** — Pure Pydantic data models: `PlanPilotConfig`, `PlanPaths`, `FieldConfig`
2. **Config loader (SDK layer)** — `load_config()` function (see [sdk.md](sdk.md))

The config domain has **no dependencies** on any other domain. See [contracts.md](../design/contracts.md) for where it fits in the domain hierarchy.

## FieldConfig

Project field preferences. Controls which field values the provider sets on created items.

```python
class FieldConfig(BaseModel):
    status: str = "Backlog"
    """Status field value (e.g. "Backlog", "In Progress")."""

    priority: str = "P1"
    """Priority field value (e.g. "P1", "P2")."""

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
        "EPIC": "Epic", "STORY": "Story", "TASK": "Task",
    }
    """Plan item type -> provider value mapping for create_type_strategy."""
```

**Cross-provider field mapping:** These names use GitHub Projects v2 terminology as defaults. Providers interpret them in their own context:

| FieldConfig field | GitHub | Jira |
|-------------------|--------|------|
| `status` | Status column | Workflow status |
| `priority` | Priority field | Priority field |
| `iteration` | Iteration field | Sprint |
| `size_field` | Custom "Size" field | Story points field |
| `create_type_strategy` | Issue type or label strategy | Issue type or label strategy |

If a configured field does not exist in the provider target, provider setup must fail fast with a clear error.

## PlanPaths

Supports two mutually exclusive modes:

```python
class PlanPaths(BaseModel):
    epics: Path | None = None
    stories: Path | None = None
    tasks: Path | None = None
    unified: Path | None = None
```

| Rule | Description |
|------|------------|
| Mutual exclusivity | If `unified` is set, none of `epics`/`stories`/`tasks` may be set |
| At least one path | At least one of the four fields must be non-None |
| Multi-file minimum | In multi-file mode, at least one path must be set (partial plans allowed) |

## PlanPilotConfig

```python
class PlanPilotConfig(BaseModel):
    provider: str
    """Provider name (e.g. "github"). Must match a registered provider."""

    target: str
    """Target designation (e.g. "owner/repo" for GitHub)."""

    auth: str = "gh-cli"
    """Auth method. For GitHub: "gh-cli", "env", or "token"."""

    token: str | None = None
    """Static auth token. Only used when auth="token"."""

    board_url: str
    """Project board URL. Required for v2 GitHub launch."""

    plan_paths: PlanPaths
    """Paths to plan JSON files."""

    validation_mode: str = "strict"
    """Plan validation: "strict" or "partial"."""

    sync_path: Path = Path("sync-map.json")
    """Path for apply-mode sync map. Dry-run writes to <sync_path>.dry-run."""

    label: str = "planpilot"
    """Label to apply to all created items."""

    max_concurrent: int = Field(default=1, ge=1)
    """Max concurrent provider operations per engine phase. Default 1 = sequential."""

    field_config: FieldConfig = FieldConfig()
    """Project field preferences."""

    model_config = {"frozen": True}
```

### Auth/Token Validation

| `auth` value | `token` value | Result |
|--------------|---------------|--------|
| `"gh-cli"` | `None` | Valid |
| `"env"` | `None` | Valid |
| `"token"` | non-empty string | Valid |
| `"token"` | `None` / empty | Invalid (`ConfigError`) |
| `"gh-cli"` or `"env"` | non-empty string | Invalid (`ConfigError`, prevents ambiguous secret source) |

### max_concurrent Validation

| `max_concurrent` value | Result |
|------------------------|--------|
| `1` (default) | Valid — fully sequential |
| `2`–`100` | Valid — concurrent within engine phases |
| `0` or negative | Invalid (`ConfigError`) |

### GitHub-Specific Config Rules (v2 launch)

- `board_url` is required and must be a GitHub Projects v2 URL
- Owner type resolved from URL shape:
  - `https://github.com/orgs/<org>/projects/<n>` -> organization-owned
  - `https://github.com/users/<user>/projects/<n>` -> user-owned
- User-owned projects must use `create_type_strategy: "label"`
- Unsupported strategy/capability combinations fail at provider setup

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| `provider` / `auth` are strings, not enums | Open for extension |
| `board_url` required for GitHub launch | v2 scope excludes repo-only sync |
| `validation_mode` is persisted config | Partial plan workflows must be explicit and repeatable |
| No `dry_run` field | Per-invocation execution mode, passed as `sync(dry_run=...)` |
| No `verbose` field | Logging is a CLI concern |
| `max_concurrent` defaults to 1 | Sequential by default — opt-in concurrency, no surprises |
| `frozen = True` | Prevents accidental mutation during sync |

## Path Resolution

All paths are resolved relative to the config file's parent directory by `load_config()`.

| Field | Resolution |
|-------|-----------|
| `plan_paths.*` | Relative to config file directory |
| `sync_path` | Relative to config file directory |
| Dry-run output | Derived: `sync_path` + `.dry-run` suffix |

## JSON Schema Examples

**Full config:**

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
  "max_concurrent": 5,
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

**Minimal config:**

```json
{
  "provider": "github",
  "target": "owner/repo",
  "board_url": "https://github.com/orgs/owner/projects/1",
  "plan_paths": { "unified": "plan.json" }
}
```

## File Structure

```
src/planpilot/
├── contracts/
│   └── config.py          # PlanPilotConfig, PlanPaths, FieldConfig
├── sdk.py                 # load_config() lives here
└── exceptions.py          # ConfigError
```
