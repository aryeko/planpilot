# Providers Module Spec

The providers module (`providers/`) contains concrete implementations of the `Provider` ABC and a factory for instantiation by name. Each provider adapts an external issue-tracking system (GitHub, Jira, Linear) to the provider contract.

This is a Core module. It depends only on the Contracts layer (see [contracts.md](../design/contracts.md) for `Provider`, `Item`, and input/filter type definitions).

Third-party/runtime dependencies (e.g. httpx, generated GraphQL client) are allowed; "depends only on Contracts" means no imports from other PlanPilot internal layers.

**Module-level base class:** `ProviderContext` (defined in `providers/base.py`, Core layer) is a base class that concrete providers subclass to store resolved IDs, field mappings, and other provider-specific state. Opaque to the engine and SDK.

## Required Discovery Capabilities

Providers must support discovery semantics used by the engine:

- `search_items()` must apply `labels` and `body_contains` as a conjunctive filter
- `search_items()` must use provider-native search semantics with mandatory pagination
- Discovery must fail fast if search limits/caps would truncate results (no silent partial discovery)
- If a provider cannot satisfy these semantics, it must fail fast in `__aenter__` with `ProviderCapabilityError`

## Partial Failure Error Contract

`create_item()` is multi-step and may fail after an item already exists remotely:

```python
class CreateItemPartialFailureError(ProviderError):
    created_item_id: str | None
    created_item_key: str | None
    created_item_url: str | None
    completed_steps: tuple[str, ...]   # canonical step names
    retryable: bool
```

Canonical step names: `issue_created`, `issue_type_set`, `labels_set`, `project_item_added`, `project_fields_set`.

## Key Design: `create_item()` is Idempotent Multi-Step

In v2, `create_item()` handles everything the v1 engine orchestrated across multiple calls, as a re-runnable workflow:

```mermaid
flowchart TB
    Start["create_item(input)"] --> CreateIssue["1. Create issue<br/>(with metadata in body)"]
    CreateIssue --> EnsureType{"create_type_strategy?"}
    EnsureType -- issue-type --> SetType["2a. Ensure issue type"]
    EnsureType -- label --> SetLabel["2b. Ensure type label"]
    SetType --> EnsureLabels["3. Ensure discovery label"]
    SetLabel --> EnsureLabels
    EnsureLabels --> AddProject["4. Ensure project item"]
    AddProject --> SetFields{"size / fields?"}
    SetFields -- Yes --> EnsureFields["5. Ensure project fields"]
    SetFields -- No --> Done
    EnsureFields --> Done["Return GitHubItem"]

    CreateIssue -.->|"failure after step N"| PartialError["Raise CreateItemPartialFailureError<br/>with created_item_id + completed_steps"]
```

**Required behavior:**
- Each sub-step must be safe to retry (`ensure_*` semantics)
- Partial failures must raise `CreateItemPartialFailureError` with created item identity + `completed_steps`
- Re-running sync must converge to one correctly configured item, not duplicates
- Metadata must be present in body at issue creation time so discovery can find partially configured items

## Key Design: Reconciliation Ownership

`update_item()` applies only plan-authoritative fields: `title`, `body`, `item_type`, `labels`, `size`.

- **Labels:** Additive (`ensure label present`), not replace-all. Provider must preserve non-PlanPilot labels.
- **Provider-authoritative after create:** `status`, `priority`, `iteration` from `field_config` are creation defaults, not continuously enforced.

## Provider Factory

```python
PROVIDERS: dict[str, type[Provider]] = {
    "github": GitHubProvider,
}

def create_provider(
    name: str, *, target: str, token: str, board_url: str,
    label: str = "planpilot", field_config: FieldConfig | None = None,
    **kwargs: object,
) -> Provider:
    """Create a provider instance by name.

    Raises:
        ValueError: If name is not in PROVIDERS.
    """
```

## GitHub Provider

Launch provider for GitHub Issues + Projects v2. Uses ariadne-codegen + httpx for typed async GraphQL (see [ADR-001](../decisions/001-ariadne-codegen.md) for rationale).

See [github-provider.md](github-provider.md) for full implementation details: core classes, authentication, codegen setup, operational hardening, operations inventory, and file structure.

## Adding a New Provider

1. Create `providers/jira/` package
2. Implement `JiraProvider(Provider)` with all abstract methods
3. Implement `JiraItem(Item)` with `set_parent()` and `add_dependency()`
4. Create API transport client
5. Add to factory mapping in `providers/factory.py`

No changes needed to engine, SDK, CLI, renderers, or any other module.
