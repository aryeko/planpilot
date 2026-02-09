# Renderers Module Spec

## Overview

The renderers module (`renderers/`) contains concrete implementations of the `BodyRenderer` ABC and a factory for instantiation by name. Each renderer transforms a `PlanItem` + `RenderContext` into a formatted body string for a specific markup language.

This is a Core (L2) module. It depends only on the Contracts layer.

## Dependencies (Contracts only)

| Contract Domain | Types Used |
|----------------|-----------|
| **plan** | `PlanItem`, `Scope`, `SpecRef`, `Estimate`, `Verification` |
| **renderer** | `BodyRenderer` ABC, `RenderContext` |

No dependency on provider, item, sync, config, or engine.

## BodyRenderer Contract (recap)

Defined in the renderer domain of Contracts:

```python
class BodyRenderer(ABC):
    @abstractmethod
    def render(self, item: PlanItem, context: RenderContext) -> str:
        """Render body for any plan item.

        Args:
            item: The PlanItem (Epic, Story, or Task).
            context: Resolved cross-references and metadata.

        Returns:
            Formatted body string.
        """
```

## RenderContext Contract (recap)

```python
class RenderContext:
    plan_id: str                              # Deterministic plan hash
    parent_ref: str | None                    # Human-readable ref to parent (e.g. "#42"), None for epics
    sub_items: list[tuple[str, str]]          # (key, title) of child items
    dependencies: dict[str, str]              # {dep_id: issue_ref} for blocked-by links
```

## MarkdownRenderer

Concrete implementation for GitHub-flavored Markdown.

```python
class MarkdownRenderer(BodyRenderer):
    def render(self, item: PlanItem, context: RenderContext) -> str: ...
```

### Rendering Strategy

The renderer uses a **field-driven** approach: it iterates over the item's fields and renders each non-empty one as a Markdown section. Empty/None fields are skipped.

### Output Structure

The rendered body follows this template (sections included only when the field has content):

```markdown
<!-- PLAN_ID: {context.plan_id} -->
<!-- ITEM_ID: {item.id} -->

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

## Spec Reference

* {item.spec_ref formatted}

## Success Metrics

* {item.success_metrics items}

## Sub-items

* [ ] {key} {title}  (for each in context.sub_items)

## Dependencies

Blocked by:

* {ref}  (for each in context.dependencies)
```

### Section Rendering Rules

| Section | Rendered When | Format |
|---------|--------------|--------|
| PLAN_ID marker | Always | HTML comment |
| ITEM_ID marker | Always | HTML comment |
| Goal | `item.goal` is non-empty | Plain text |
| Motivation | `item.motivation` is non-empty | Plain text |
| Parent | `context.parent_ref` is not None | Bullet with ref |
| Scope | `item.scope` has in_scope or out_scope | In/Out bullet lists |
| Requirements | `item.requirements` is non-empty | Bullet list |
| Acceptance Criteria | `item.acceptance_criteria` is non-empty | Bullet list |
| Assumptions | `item.assumptions` is non-empty | Bullet list |
| Risks | `item.risks` is non-empty | Bullet list |
| Estimate | `item.estimate` has tshirt or hours | Inline text |
| Verification | `item.verification` has any content | Sub-sections per field |
| Spec Reference | `item.spec_ref` is non-empty | Formatted link |
| Success Metrics | `item.success_metrics` is non-empty (Story only) | Bullet list |
| Sub-items | `context.sub_items` is non-empty | Checklist |
| Dependencies | `context.dependencies` is non-empty | Blocked-by list |

### Helper Functions

Internal to the renderers module (not Contracts):

| Helper | Signature | Purpose |
|--------|-----------|---------|
| `bullets` | `(items: list[str]) -> str` | Render bullet list, "* (none)" if empty |
| `scope_block` | `(scope: Scope) -> str` | Render In/Out scope block |
| `spec_ref_block` | `(spec_ref: SpecRef or str) -> str` | Format spec reference with link/section/quote |

## RendererFactory

Registry + factory for creating renderers by name.

```python
class RendererFactory:
    _registry: dict[str, type[BodyRenderer]] = {}

    @classmethod
    def register(cls, name: str, renderer_cls: type[BodyRenderer]) -> None:
        """Register a renderer class by name."""

    @classmethod
    def create(cls, name: str, **kwargs: object) -> BodyRenderer:
        """Create a renderer instance by name.

        Args:
            name: Renderer name (must be registered).

        Returns:
            BodyRenderer instance.

        Raises:
            ValueError: If name is not registered.
        """
```

### Registration

Concrete renderers self-register on import:

```python
# renderers/markdown.py
from planpilot.renderers.factory import RendererFactory

class MarkdownRenderer(BodyRenderer):
    ...

RendererFactory.register("markdown", MarkdownRenderer)
```

## File Structure

```
renderers/
├── __init__.py
├── factory.py          # RendererFactory
├── markdown.py         # MarkdownRenderer + helpers
└── (future: wiki.py)   # WikiRenderer for Jira
```

## Changes from v1

| v1 | v2 | Rationale |
|----|-----|-----------|
| Three methods: `render_epic()`, `render_story()`, `render_task()` | Single `render(item, context)` | Decoupled from entity types |
| Separate `render_checklist()`, `render_deps_block()` | Integrated into `render()` via RenderContext | Single responsibility |
| `components.py` shared helpers | Same helpers, internal to renderers module | No change in approach |
| No factory | `RendererFactory` with registration | Pluggable renderers |
| `BodyRenderer` was a Protocol in rendering/base.py | `BodyRenderer` is an ABC in Contracts | Moved to Contracts layer |
