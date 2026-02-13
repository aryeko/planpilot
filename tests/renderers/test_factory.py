import pytest

from planpilot.core.renderers.factory import create_renderer
from planpilot.core.renderers.markdown import MarkdownRenderer


def test_create_renderer_returns_markdown_renderer() -> None:
    renderer = create_renderer("markdown")

    assert isinstance(renderer, MarkdownRenderer)


def test_create_renderer_unknown_name_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown renderer: unknown"):
        create_renderer("unknown")
