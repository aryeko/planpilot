"""Renderer factory."""

from __future__ import annotations

from planpilot_v2.contracts.renderer import BodyRenderer
from planpilot_v2.renderers.markdown import MarkdownRenderer

RENDERERS: dict[str, type[BodyRenderer]] = {"markdown": MarkdownRenderer}


def create_renderer(name: str, **kwargs: object) -> BodyRenderer:
    renderer_cls = RENDERERS.get(name)
    if renderer_cls is None:
        raise ValueError(f"Unknown renderer: {name}")
    return renderer_cls(**kwargs)
