"""Issue-body rendering for planpilot.

The :class:`BodyRenderer` protocol defines the contract;
:class:`MarkdownRenderer` is the default implementation.
"""

from planpilot.rendering.base import BodyRenderer
from planpilot.rendering.markdown import MarkdownRenderer

__all__ = ["BodyRenderer", "MarkdownRenderer"]
