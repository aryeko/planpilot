# Renderers Module Spec

The renderers module (`renderers/`) contains concrete implementations of the `BodyRenderer` ABC and a factory for instantiation by name. Each renderer transforms a `PlanItem` + `RenderContext` into a formatted body string for a specific markup language.

This is a Core module. It depends only on the Contracts layer (see [contracts.md](../design/contracts.md) for `BodyRenderer`, `RenderContext`, and `PlanItem` definitions).

## MarkdownRenderer

Concrete implementation for GitHub-flavored Markdown.

```python
class MarkdownRenderer(BodyRenderer):
    def render(self, item: PlanItem, context: RenderContext) -> str: ...
```

### Rendering Strategy

Field-driven: iterates over the item's fields and renders each non-empty one as a Markdown section. Empty/None fields are skipped.

The renderer must render only provided fields from `PlanItem` and `RenderContext`; unresolved references are omitted by the engine in partial mode.

### Output Structure

Sections are included only when the field has content:

```markdown
PLANPILOT_META_V1
PLAN_ID:{context.plan_id}
ITEM_ID:{item.id}
END_PLANPILOT_META

## Goal

{item.goal}

## Motivation

{item.motivation}

## Parent

* {context.parent_ref}

## Scope

In:

* {item.scope.in_scope items}

Out:

* {item.scope.out_scope items}

## Requirements

* {item.requirements items}

## Acceptance Criteria

* {item.acceptance_criteria items}

## Assumptions

* {item.assumptions items}

## Risks

* {item.risks items}

## Estimate

{item.estimate.tshirt} ({item.estimate.hours}h)

## Verification

Commands:

* {item.verification.commands items}

CI checks:

* {item.verification.ci_checks items}

Evidence:

* {item.verification.evidence items}

Manual steps:

* {item.verification.manual_steps items}

## Spec Reference

* {item.spec_ref formatted}

## Success Metrics

* {item.success_metrics items}

## Sub-items

* [ ] {key} {title}  (for each in sorted(context.sub_items))

## Dependencies

Blocked by:

* {ref}  (for each in dependencies sorted by dep_id)
```

### Section Rendering Rules

| Section | Rendered When | Format |
|---------|--------------|--------|
| Metadata block | Always | Plain text (`PLANPILOT_META_V1` ... `END_PLANPILOT_META`) |
| Goal | `item.goal` is non-empty | Plain text |
| Motivation | `item.motivation` is non-empty | Plain text |
| Parent | `context.parent_ref` is not None | Bullet with ref |
| Scope | `item.scope` has content | In/Out bullet lists |
| Requirements | `item.requirements` is non-empty | Bullet list |
| Acceptance Criteria | `item.acceptance_criteria` is non-empty | Bullet list |
| Assumptions | `item.assumptions` is non-empty | Bullet list |
| Risks | `item.risks` is non-empty | Bullet list |
| Estimate | `item.estimate` has tshirt or hours | Inline text |
| Verification | `item.verification` has any content | Sub-sections per field |
| Spec Reference | `item.spec_ref` is non-empty | Formatted link |
| Success Metrics | `item.success_metrics` is non-empty | Bullet list |
| Sub-items | `context.sub_items` is non-empty | Checklist |
| Dependencies | `context.dependencies` is non-empty | Blocked-by list |

### Metadata Block Requirements

- Every renderer must emit the metadata block verbatim at the top of the body.
- The block is provider-searchable and engine-parseable; do not wrap in renderer-specific comments.
- Values are single-line tokens without extra spaces around `:`.

### Deterministic Ordering Requirements

- Renderers must produce byte-stable output for identical inputs.
- `context.sub_items` rendered in deterministic order (`key`, then `title`).
- `context.dependencies` rendered in deterministic order by dependency ID.
- Ordering must not depend on insertion order from provider responses.

### Helper Functions

Internal to the renderers module:

| Helper | Signature | Purpose |
|--------|-----------|---------|
| `bullets` | `(items: list[str]) -> str` | Render bullet list |
| `scope_block` | `(scope: Scope) -> str` | Render In/Out scope block |
| `spec_ref_block` | `(spec_ref: SpecRef \| str) -> str` | Format spec reference with link/section/quote |

## Renderer Factory

```python
RENDERERS: dict[str, type[BodyRenderer]] = {
    "markdown": MarkdownRenderer,
}

def create_renderer(name: str, **kwargs: object) -> BodyRenderer:
    """Create a renderer instance by name.

    Raises:
        ValueError: If name is not in RENDERERS.
    """
```

## File Structure

```
renderers/
├── __init__.py
├── factory.py          # create_renderer factory
├── markdown.py         # MarkdownRenderer + helpers
└── (future: wiki.py)   # WikiRenderer for Jira
```
