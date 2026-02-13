"""Public API surface for PlanPilot."""

__version__ = "2.3.0"

from planpilot.auth import create_token_resolver
from planpilot.config import (
    create_plan_stubs,
    detect_plan_paths,
    detect_target,
    load_config,
    scaffold_config,
    write_config,
)
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
from planpilot.contracts.init import InitProgress
from planpilot.contracts.plan import Plan, PlanItem, PlanItemType
from planpilot.contracts.provider import Provider
from planpilot.contracts.renderer import BodyRenderer, RenderContext
from planpilot.contracts.sync import CleanResult, MapSyncResult, SyncEntry, SyncMap, SyncResult
from planpilot.init import (
    create_init_token_resolver,
    resolve_init_token,
    validate_board_url,
    validate_github_auth_for_init,
)
from planpilot.providers import create_provider
from planpilot.renderers import create_renderer
from planpilot.sdk import PlanPilot, load_plan

__all__ = [
    "AuthenticationError",
    "BodyRenderer",
    "CleanResult",
    "ConfigError",
    "FieldConfig",
    "InitProgress",
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
    "create_init_token_resolver",
    "create_plan_stubs",
    "create_provider",
    "create_renderer",
    "create_token_resolver",
    "detect_plan_paths",
    "detect_target",
    "load_config",
    "load_plan",
    "resolve_init_token",
    "scaffold_config",
    "validate_board_url",
    "validate_github_auth_for_init",
    "write_config",
]
