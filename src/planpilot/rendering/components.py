"""Reusable rendering components for issue body generation."""

from __future__ import annotations

from planpilot.models.plan import Scope, SpecRef


def bullets(items: list[str]) -> str:
    """Render a bullet list, or '* (none)' if empty.

    Args:
        items: List of strings to render as bullets.

    Returns:
        Markdown bullet list string, or '* (none)' if empty.
    """
    if not items:
        return "* (none)"
    return "\n".join(f"* {i}" for i in items)


def scope_block(scope: Scope) -> str:
    """Render an in-scope / out-of-scope block.

    Args:
        scope: Scope model with in_scope and out_scope lists.

    Returns:
        Markdown formatted scope block with In/Out sections.
    """
    return f"In:\n\n{bullets(scope.in_scope)}\n\nOut:\n\n{bullets(scope.out_scope)}"


def spec_ref_block(spec_ref: SpecRef | str | None) -> str:
    """Render a spec reference block.

    Handles string, SpecRef model, or None/empty values.

    Args:
        spec_ref: Spec reference as string, SpecRef model, or None.

    Returns:
        Markdown formatted spec reference block.
    """
    if isinstance(spec_ref, str):
        ref = spec_ref.strip()
        return f"* {ref}" if ref else "* (none)"
    if isinstance(spec_ref, SpecRef):
        path = spec_ref.path.strip()
        if not path:
            return "* (none)"
        anchor = spec_ref.anchor.strip()
        link = f"{path}#{anchor}" if anchor else path
        lines = [f"* {link}"]
        if spec_ref.section.strip():
            lines.append(f"* Section: {spec_ref.section.strip()}")
        if spec_ref.quote.strip():
            lines.append(f"* Quote: {spec_ref.quote.strip()}")
        return "\n".join(lines)
    return "* (none)"
