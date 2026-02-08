# Migration Guide

## From v0.2 to the architecture redesign

The architecture redesign introduces breaking changes to the CLI, Python API, and internal module structure. Plan file schemas are **unchanged** -- no modifications to your `epics.json`, `stories.json`, or `tasks.json` files are required.

### CLI changes

| What | Old | New |
|------|-----|-----|
| T-shirt size flag | `--size-from-tshirt true` / `--size-from-tshirt false` | Enabled by default; use `--no-size-from-tshirt` to disable |

All other CLI flags are unchanged.

### Python API changes

| What | Old | New |
|------|-----|-----|
| Sync entry point | `run_sync(args)` | `SyncEngine(provider, renderer, config).sync()` |
| Configuration | `argparse.Namespace` | `SyncConfig` (Pydantic `BaseModel`) |
| File load errors | `RuntimeError` | `PlanLoadError` (subclass of `PlanPilotError`) |
| Body rendering | `body_render.py` functions | `BodyRenderer` Protocol / `MarkdownRenderer` |
| GitHub API | `github_api.py` functions | `GhClient` async wrapper + `GitHubProvider` |

### Removed modules

The following modules were replaced by the new package structure:

| Removed | Replaced by |
|---------|-------------|
| `sync.py` | `sync/engine.py` (`SyncEngine`) |
| `github_api.py` | `providers/github/client.py` (`GhClient`) |
| `body_render.py` | `rendering/markdown.py` (`MarkdownRenderer`) |
| `utils.py` | `providers/github/mapper.py` + `rendering/components.py` |
| `types.py` | `models/plan.py`, `models/project.py`, `models/sync.py` |
| `relations.py` | `sync/relations.py` |
| `project_fields.py` | `providers/github/provider.py` |

### New exception hierarchy

All planpilot exceptions now inherit from `PlanPilotError`:

```
PlanPilotError
├── PlanLoadError          # File I/O or JSON parse failures
├── PlanValidationError    # Relational integrity errors
├── AuthenticationError    # gh auth failures
├── ProviderError          # Provider API call failures
├── ProjectURLError        # Invalid project URL format
└── SyncError              # Non-recoverable sync failures
```

Catching `PlanPilotError` handles all of the above.

---

## From plan-gh-project-sync to planpilot

### Package rename

The project was renamed from `plan-gh-project-sync` to `planpilot` in v0.2.0.

| What | Old | New |
|------|-----|-----|
| PyPI package | `plan-gh-project-sync` | `planpilot` |
| Python import | `plan_gh_project_sync` | `planpilot` |
| CLI command | `plan-gh-project-sync` | `planpilot` |
| Module run | `python -m plan_gh_project_sync` | `python -m planpilot` |

### Install the new package

```bash
pip install planpilot
# or
poetry add planpilot
```

### Update CLI invocations

```bash
# Old
plan-gh-project-sync --repo owner/repo --project-url ... --dry-run

# New
planpilot --repo owner/repo --project-url ... --dry-run
```

### Slicing helper

The `tools/slice_epics_for_sync.py` script has been replaced with a proper CLI entry point:

```bash
# Old
PYTHONPATH=src python3 tools/slice_epics_for_sync.py --epics-path ...

# New
planpilot-slice --epics-path ...
```

### Stricter validation (v0.2.0)

v0.2.0 enforces all required fields and removes silent fallbacks:

| What changed | Old behavior | New behavior |
|---|---|---|
| Missing `epic_id` on story | Fell back to first epic's ID | Validation error |
| Missing `story_ids` on epic | Used all stories in order | Validation error |
| Missing `task_ids` on story | Fell back to `story_ids` key (typo) | Validation error |
| Missing `goal`, `spec_ref`, etc. | Silent empty section in issue body | Validation error |

If your existing plan files relied on these fallbacks, add the missing fields before upgrading. See [schemas.md](schemas.md) for the full list of required fields.
