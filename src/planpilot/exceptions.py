"""Custom exception hierarchy for planpilot.

All planpilot exceptions inherit from :class:`PlanPilotError`, making it easy
to catch any library error with a single ``except`` clause while still allowing
callers to handle specific failure modes.
"""

from __future__ import annotations


class PlanPilotError(Exception):
    """Base exception for all planpilot errors."""


class PlanLoadError(PlanPilotError):
    """Raised when plan files cannot be read or parsed."""


class PlanValidationError(PlanPilotError):
    """Raised when plan JSON fails schema or relational validation.

    Attributes:
        errors: Individual validation error messages.
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        joined = "\n".join(f"  - {e}" for e in errors)
        super().__init__(f"Plan validation failed:\n{joined}")


class AuthenticationError(PlanPilotError):
    """Raised when the provider cannot authenticate."""


class ProviderError(PlanPilotError):
    """Raised when a provider API call fails unexpectedly."""


class ProjectURLError(PlanPilotError):
    """Raised when a project URL cannot be parsed."""


class SyncError(PlanPilotError):
    """Raised when the sync engine encounters a non-recoverable failure."""
