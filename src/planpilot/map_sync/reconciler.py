"""Discovery reconciliation for map-sync workflows."""

from __future__ import annotations

from planpilot.contracts.item import Item
from planpilot.contracts.plan import PlanItem
from planpilot.contracts.sync import SyncEntry, to_sync_entry
from planpilot.map_sync.parser import RemotePlanParser
from planpilot.metadata import parse_metadata_block


class MapSyncReconciler:
    def __init__(self, *, parser: RemotePlanParser | None = None) -> None:
        self._parser = parser or RemotePlanParser()

    def reconcile_discovered_items(
        self,
        *,
        discovered_items: list[Item],
        plan_id: str,
    ) -> tuple[dict[str, SyncEntry], dict[str, PlanItem]]:
        desired_entries: dict[str, SyncEntry] = {}
        remote_plan_items: dict[str, PlanItem] = {}

        for item in discovered_items:
            metadata = parse_metadata_block(item.body)
            if metadata.get("PLAN_ID") != plan_id:
                continue
            item_id = metadata.get("ITEM_ID")
            if not item_id:
                continue

            desired_entries[item_id] = to_sync_entry(item)
            remote_plan_items[item_id] = self._parser.plan_item_from_remote(
                item_id=item_id,
                metadata=metadata,
                title=item.title,
                body=item.body,
            )

        return desired_entries, remote_plan_items
