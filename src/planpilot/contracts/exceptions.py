"""Exception hierarchy for PlanPilot v2."""

from __future__ import annotations


class PlanPilotError(Exception):
    """Base exception for all PlanPilot errors."""


class ConfigError(PlanPilotError):
    """Configuration loading or validation failure."""


class PlanLoadError(PlanPilotError):
    """Plan file loading/parsing failure."""


class PlanValidationError(PlanPilotError):
    """Plan semantic validation failure."""


class ProviderError(PlanPilotError):
    """Base provider operation failure."""


class ProviderCapabilityError(ProviderError):
    """Provider lacks required capability."""

    def __init__(self, message: str, *, capability: str) -> None:
        super().__init__(message)
        self.capability = capability


class CreateItemPartialFailureError(ProviderError):
    """Provider created item but failed to complete downstream mutation steps."""

    def __init__(
        self,
        message: str,
        *,
        created_item_id: str | None = None,
        created_item_key: str | None = None,
        created_item_url: str | None = None,
        completed_steps: tuple[str, ...] = (),
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.created_item_id = created_item_id
        self.created_item_key = created_item_key
        self.created_item_url = created_item_url
        self.completed_steps = completed_steps
        self.retryable = retryable


class AuthenticationError(ProviderError):
    """Authentication/authorization failure."""


class ProjectURLError(ProviderError):
    """Project/board URL is invalid or unsupported."""


class SyncError(PlanPilotError):
    """Engine-level synchronization failure."""
