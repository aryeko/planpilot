"""Sync operation helpers for PlanPilot SDK."""

from __future__ import annotations

from typing import TYPE_CHECKING

from planpilot.contracts.exceptions import ProviderError
from planpilot.contracts.plan import Plan
from planpilot.contracts.provider import Provider
from planpilot.contracts.sync import SyncResult
from planpilot.engine import SyncEngine
from planpilot.plan import PlanLoader, PlanValidator
from planpilot.providers.dry_run import DryRunProvider

if TYPE_CHECKING:
    from planpilot.sdk import PlanPilot


async def run_sync(sdk: PlanPilot, plan: Plan | None, *, dry_run: bool) -> SyncResult:
    import planpilot.sdk as sdk_module

    loaded_plan = plan if plan is not None else PlanLoader().load(sdk._config.plan_paths)
    PlanValidator().validate(loaded_plan, mode=sdk._config.validation_mode)
    plan_id = sdk_module.PlanHasher().compute_plan_id(loaded_plan)

    try:
        if dry_run:
            provider: Provider = DryRunProvider()
            result = await SyncEngine(provider, sdk._renderer, sdk._config, dry_run=True, progress=sdk._progress).sync(
                loaded_plan, plan_id
            )
        else:
            provider = await sdk._resolve_apply_provider()
            async with provider:
                result = await SyncEngine(
                    provider,
                    sdk._renderer,
                    sdk._config,
                    dry_run=False,
                    progress=sdk._progress,
                ).sync(loaded_plan, plan_id)
    except* ProviderError as provider_errors:
        raise provider_errors.exceptions[0] from None

    sdk._persist_sync_map(result.sync_map, dry_run=dry_run)
    return result
