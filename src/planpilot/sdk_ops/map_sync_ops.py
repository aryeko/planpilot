"""Map-sync operation helpers for PlanPilot SDK."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from planpilot.contracts.exceptions import ProviderError
from planpilot.contracts.item import ItemSearchFilters
from planpilot.contracts.plan import PlanItem
from planpilot.contracts.sync import MapSyncResult, SyncEntry, SyncMap
from planpilot.metadata import parse_metadata_block

if TYPE_CHECKING:
    from planpilot.sdk import PlanPilot


async def discover_remote_plan_ids(sdk: PlanPilot) -> list[str]:
    if sdk._progress is not None:
        sdk._progress.phase_start("Map Plan IDs")
    provider = await sdk._resolve_apply_provider()
    try:
        async with provider:
            items = await provider.search_items(ItemSearchFilters(labels=[sdk._config.label]))
    except* ProviderError as provider_errors:
        if sdk._progress is not None:
            sdk._progress.phase_error("Map Plan IDs", provider_errors.exceptions[0])
        raise provider_errors.exceptions[0] from None

    plan_ids = {
        metadata["PLAN_ID"]
        for item in items
        for metadata in [parse_metadata_block(item.body)]
        if metadata.get("PLAN_ID")
    }
    if sdk._progress is not None:
        sdk._progress.phase_done("Map Plan IDs")
    return sorted(plan_ids)


async def run_map_sync(sdk: PlanPilot, *, plan_id: str, dry_run: bool) -> MapSyncResult:
    current = sdk._load_sync_map(plan_id=plan_id)

    if sdk._progress is not None:
        sdk._progress.phase_start("Map Discover")
    provider = await sdk._resolve_apply_provider()
    try:
        async with provider:
            discovered_items = await provider.search_items(
                ItemSearchFilters(labels=[sdk._config.label], body_contains=f"PLAN_ID:{plan_id}")
            )
    except* ProviderError as provider_errors:
        if sdk._progress is not None:
            sdk._progress.phase_error("Map Discover", provider_errors.exceptions[0])
        raise provider_errors.exceptions[0] from None
    if sdk._progress is not None:
        sdk._progress.phase_done("Map Discover")

    desired_entries: dict[str, SyncEntry]
    remote_plan_items: dict[str, PlanItem]
    if sdk._progress is not None:
        sdk._progress.phase_start("Map Reconcile", total=len(discovered_items))
    desired_entries, remote_plan_items = sdk._map_sync_reconciler.reconcile_discovered_items(
        discovered_items=discovered_items,
        plan_id=plan_id,
    )
    if sdk._progress is not None:
        for _ in discovered_items:
            sdk._progress.item_done("Map Reconcile")
        sdk._progress.phase_done("Map Reconcile")

    current_entries = current.entries
    added = sorted(item_id for item_id in desired_entries if item_id not in current_entries)
    removed = sorted(item_id for item_id in current_entries if item_id not in desired_entries)
    updated = sorted(
        item_id
        for item_id in desired_entries
        if item_id in current_entries and current_entries[item_id] != desired_entries[item_id]
    )

    reconciled = SyncMap(
        plan_id=plan_id,
        target=sdk._config.target,
        board_url=sdk._config.board_url,
        entries=desired_entries,
    )
    result = MapSyncResult(
        sync_map=reconciled,
        added=added,
        removed=removed,
        updated=updated,
        plan_items_synced=len(remote_plan_items),
        dry_run=dry_run,
    )
    if not dry_run:
        if sdk._progress is not None:
            sdk._progress.phase_start("Map Persist")
        sdk._persist_sync_map(reconciled, dry_run=False)
        sdk._persist_plan_from_remote(items=remote_plan_items.values())
        if sdk._progress is not None:
            sdk._progress.phase_done("Map Persist")
    return result


def persist_plan_from_remote(sdk: PlanPilot, *, items: Iterable[PlanItem]) -> None:
    sdk._map_sync_persistence.persist_plan_from_remote(items=items, plan_paths=sdk._config.plan_paths)
