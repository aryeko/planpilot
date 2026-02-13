"""Clean operation helpers for PlanPilot SDK."""

from __future__ import annotations

from typing import TYPE_CHECKING

from planpilot.contracts.exceptions import ProviderError
from planpilot.contracts.item import Item, ItemSearchFilters
from planpilot.contracts.plan import Plan
from planpilot.contracts.provider import Provider
from planpilot.contracts.sync import CleanResult
from planpilot.metadata import parse_metadata_block
from planpilot.plan import PlanHasher, PlanLoader

if TYPE_CHECKING:
    from planpilot.sdk import PlanPilot


async def run_clean(sdk: PlanPilot, *, dry_run: bool, all_plans: bool) -> CleanResult:
    loaded_plan: Plan | None = None
    if all_plans:
        plan_id = "all-plans"
    else:
        loaded_plan = PlanLoader().load(sdk._config.plan_paths)
        plan_id = PlanHasher().compute_plan_id(loaded_plan)

    try:
        provider = await sdk._resolve_apply_provider()
        async with provider:
            items_deleted = await sdk._discover_and_delete_items(
                provider,
                plan_id,
                loaded_plan,
                dry_run=dry_run,
                all_plans=all_plans,
            )
    except* ProviderError as provider_errors:
        raise provider_errors.exceptions[0] from None

    return CleanResult(plan_id=plan_id, items_deleted=items_deleted, dry_run=dry_run)


async def discover_and_delete_items(
    sdk: PlanPilot,
    provider: Provider,
    plan_id: str,
    plan: Plan | None,
    *,
    dry_run: bool,
    all_plans: bool,
) -> int:
    if all_plans:
        filters = ItemSearchFilters(labels=[sdk._config.label])
    else:
        filters = ItemSearchFilters(labels=[sdk._config.label], body_contains=f"PLAN_ID:{plan_id}")

    if sdk._progress is not None:
        sdk._progress.phase_start("Clean Discover")
    existing_items = await provider.search_items(filters)
    if sdk._progress is not None:
        sdk._progress.phase_done("Clean Discover")

    items_to_delete: list[Item] = []
    metadata_by_provider_id: dict[str, dict[str, str]] = {}
    if sdk._progress is not None:
        sdk._progress.phase_start("Clean Filter", total=len(existing_items))
    for item in existing_items:
        metadata = parse_metadata_block(item.body)
        if not all_plans and metadata.get("PLAN_ID") != plan_id:
            if sdk._progress is not None:
                sdk._progress.item_done("Clean Filter")
            continue
        if all_plans and not metadata:
            if sdk._progress is not None:
                sdk._progress.item_done("Clean Filter")
            continue
        items_to_delete.append(item)
        metadata_by_provider_id[item.id] = metadata
        if sdk._progress is not None:
            sdk._progress.item_done("Clean Filter")
    if sdk._progress is not None:
        sdk._progress.phase_done("Clean Filter")

    ordered_items_to_delete = sdk._order_items_for_deletion(
        items_to_delete,
        metadata_by_provider_id=metadata_by_provider_id,
        plan=plan,
        all_plans=all_plans,
    )

    if sdk._progress is not None:
        sdk._progress.phase_start("Clean Delete", total=len(ordered_items_to_delete))
    if not dry_run:
        remaining = list(ordered_items_to_delete)
        while remaining:
            failed: list[Item] = []
            first_error: ProviderError | None = None
            deleted_in_pass = 0
            for item in remaining:
                try:
                    await provider.delete_item(item.id)
                    deleted_in_pass += 1
                    if sdk._progress is not None:
                        sdk._progress.item_done("Clean Delete")
                except ProviderError as exc:
                    if first_error is None:
                        first_error = exc
                    failed.append(item)
            if not failed:
                break
            if deleted_in_pass == 0:
                assert first_error is not None
                if sdk._progress is not None:
                    sdk._progress.phase_error("Clean Delete", first_error)
                raise first_error
            remaining = failed
    if sdk._progress is not None:
        sdk._progress.phase_done("Clean Delete")

    return len(items_to_delete)
