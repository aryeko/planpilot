# Phase 1: Renderers Module

**Layer:** L2 (Core)
**Branch:** `v2/renderers`
**Phase:** 1 (parallel with plan, auth, engine)
**Dependencies:** Contracts only (`planpilot_v2.contracts.plan`, `planpilot_v2.contracts.renderer`)
**Design doc:** [`../docs/modules/renderers.md`](../docs/modules/renderers.md)

---

## Files to Create

| File | Contents |
|------|----------|
| `renderers/__init__.py` | Exports `MarkdownRenderer`, `create_renderer` |
| `renderers/factory.py` | `create_renderer()` factory |
| `renderers/markdown.py` | `MarkdownRenderer` + helper functions |

---

## MarkdownRenderer Output Structure

Sections included only when field has content:

```
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

* [ ] {key} {title}

## Dependencies

Blocked by:

* {ref}
```

---

## Section Rendering Rules

| Section | Rendered When | Format |
|---------|--------------|--------|
| Metadata block | Always | Plain text |
| Goal | `item.goal` is non-empty | Plain text |
| Motivation | `item.motivation` is non-empty | Plain text |
| Parent | `context.parent_ref` is not None | Bullet with ref |
| Scope | `item.scope` has content | In/Out bullet lists |
| Requirements | `item.requirements` is non-empty | Bullet list |
| Acceptance Criteria | `item.acceptance_criteria` is non-empty | Bullet list |
| Assumptions | `item.assumptions` is non-empty | Bullet list |
| Risks | `item.risks` is non-empty | Bullet list |
| Estimate | `item.estimate` has tshirt or hours | Inline text |
| Verification | `item.verification` has any content | Sub-sections |
| Spec Reference | `item.spec_ref` is non-empty | Formatted link |
| Success Metrics | `item.success_metrics` is non-empty | Bullet list |
| Sub-items | `context.sub_items` is non-empty | Checklist |
| Dependencies | `context.dependencies` is non-empty | Blocked-by list |

---

## Requirements

- Metadata block emitted verbatim at top, not wrapped in comments
- **Deterministic ordering:** byte-stable output for identical inputs. `sub_items` sorted by (key, title). `dependencies` sorted by dep_id.
- Empty/None fields are skipped entirely (no empty sections)

---

## Helper Functions

```python
def bullets(items: list[str]) -> str: ...
def scope_block(scope: Scope) -> str: ...
def spec_ref_block(spec_ref: SpecRef | str) -> str: ...
```

---

## Factory

```python
RENDERERS: dict[str, type[BodyRenderer]] = {"markdown": MarkdownRenderer}

def create_renderer(name: str, **kwargs: object) -> BodyRenderer:
    """Raises ValueError if unknown."""
```

---

## Test Strategy

| Test File | Key Cases |
|-----------|-----------|
| `test_markdown.py` | Metadata block always present, each section rendered when present, each section skipped when empty, deterministic ordering of sub_items/deps, full item renders complete body, minimal item renders only metadata+goal |
| `test_factory.py` | "markdown" -> MarkdownRenderer, unknown -> ValueError |
