"""Public API surface for PlanPilot."""

__version__ = "2.2.0"

from planpilot.auth import create_token_resolver
from planpilot.contracts.config import FieldConfig, PlanPaths, PlanPilotConfig
from planpilot.contracts.exceptions import (
    AuthenticationError,
    ConfigError,
    PlanLoadError,
    PlanPilotError,
    PlanValidationError,
    ProviderError,
    SyncError,
)
from planpilot.contracts.plan import Plan, PlanItem, PlanItemType
from planpilot.contracts.provider import Provider
from planpilot.contracts.renderer import BodyRenderer, RenderContext
from planpilot.contracts.sync import CleanResult, MapSyncResult, SyncEntry, SyncMap, SyncResult
from planpilot.providers import create_provider
from planpilot.renderers import create_renderer
from planpilot.scaffold import create_plan_stubs, detect_plan_paths, detect_target, scaffold_config, write_config
from planpilot.sdk import PlanPilot, load_config, load_plan

__all__ = [
    "AuthenticationError",
    "BodyRenderer",
    "CleanResult",
    "ConfigError",
    "FieldConfig",
    "MapSyncResult",
    "Plan",
    "PlanItem",
    "PlanItemType",
    "PlanLoadError",
    "PlanPaths",
    "PlanPilot",
    "PlanPilotConfig",
    "PlanPilotError",
    "PlanValidationError",
    "Provider",
    "ProviderError",
    "RenderContext",
    "SyncEntry",
    "SyncError",
    "SyncMap",
    "SyncResult",
    "__version__",
    "create_plan_stubs",
    "create_provider",
    "create_renderer",
    "create_token_resolver",
    "detect_plan_paths",
    "detect_target",
    "load_config",
    "load_plan",
    "scaffold_config",
    "write_config",
]
