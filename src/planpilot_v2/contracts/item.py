"""Provider-agnostic item contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from planpilot_v2.contracts.plan import PlanItemType


class Item(ABC):
    """Provider-agnostic work item."""

    @property
    @abstractmethod
    def id(self) -> str: ...  # pragma: no cover

    @property
    @abstractmethod
    def key(self) -> str: ...  # pragma: no cover

    @property
    @abstractmethod
    def url(self) -> str: ...  # pragma: no cover

    @property
    @abstractmethod
    def title(self) -> str: ...  # pragma: no cover

    @property
    @abstractmethod
    def body(self) -> str: ...  # pragma: no cover

    @property
    @abstractmethod
    def item_type(self) -> PlanItemType | None: ...  # pragma: no cover

    @abstractmethod
    async def set_parent(self, parent: Item) -> None: ...  # pragma: no cover

    @abstractmethod
    async def add_dependency(self, blocker: Item) -> None: ...  # pragma: no cover


class CreateItemInput(BaseModel):
    title: str
    body: str
    item_type: PlanItemType
    labels: list[str] = Field(default_factory=list)
    size: str | None = None


class UpdateItemInput(BaseModel):
    title: str | None = None
    body: str | None = None
    item_type: PlanItemType | None = None
    labels: list[str] | None = None
    size: str | None = None


class ItemSearchFilters(BaseModel):
    labels: list[str] = Field(default_factory=list)
    body_contains: str = ""
