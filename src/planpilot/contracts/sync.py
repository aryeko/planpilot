"""Sync map contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field

from planpilot.contracts.item import Item
from planpilot.contracts.plan import PlanItem, PlanItemType


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


class CleanResult(BaseModel):
    plan_id: str
    items_deleted: int
    dry_run: bool = False


class MapSyncResult(BaseModel):
    sync_map: SyncMap
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    updated: list[str] = Field(default_factory=list)
    candidate_plan_ids: list[str] = Field(default_factory=list)
    plan_items_synced: int = 0
    remote_plan_items: list[PlanItem] = Field(default_factory=list, exclude=True, repr=False)
    dry_run: bool = False


def to_sync_entry(item: Item) -> SyncEntry:
    return SyncEntry(id=item.id, key=item.key, url=item.url, item_type=item.item_type)
