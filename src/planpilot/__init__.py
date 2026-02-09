"""Public API surface for PlanPilot."""

__version__ = "1.2.1"

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
from planpilot.contracts.sync import SyncEntry, SyncMap, SyncResult
from planpilot.providers import create_provider
from planpilot.renderers import create_renderer
from planpilot.sdk import PlanPilot, load_config, load_plan

__all__ = [
    "AuthenticationError",
    "BodyRenderer",
    "ConfigError",
    "FieldConfig",
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
    "create_provider",
    "create_renderer",
    "create_token_resolver",
    "load_config",
    "load_plan",
]
