"""Renderer contract."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from planpilot_v2.contracts.plan import PlanItem


class RenderContext(BaseModel):
    plan_id: str
    parent_ref: str | None = None
    sub_items: list[tuple[str, str]] = Field(default_factory=list)
    dependencies: dict[str, str] = Field(default_factory=dict)


class BodyRenderer(ABC):
    @abstractmethod
    def render(self, item: PlanItem, context: RenderContext) -> str: ...  # pragma: no cover
