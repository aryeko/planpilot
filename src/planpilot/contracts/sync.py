"""Sync map contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field

from planpilot.contracts.item import Item
from planpilot.contracts.plan import PlanItemType


class SyncEntry(BaseModel):
    id: str
    key: str
    url: str
    item_type: PlanItemType | None = None


class SyncMap(BaseModel):
    plan_id: str
    target: str
    board_url: str
    entries: dict[str, SyncEntry] = Field(default_factory=dict)


class SyncResult(BaseModel):
    sync_map: SyncMap
    items_created: dict[PlanItemType, int] = Field(default_factory=dict)
    dry_run: bool = False


def to_sync_entry(item: Item) -> SyncEntry:
    return SyncEntry(id=item.id, key=item.key, url=item.url, item_type=item.item_type)
