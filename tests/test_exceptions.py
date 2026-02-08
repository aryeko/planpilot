"""Tests for planpilot exception hierarchy."""

from __future__ import annotations

from planpilot.exceptions import (
    AuthenticationError,
    PlanPilotError,
    PlanValidationError,
    ProjectURLError,
    ProviderError,
    SyncError,
)


class TestExceptionHierarchy:
    """Tests for exception inheritance."""

    def test_all_exceptions_inherit_from_plan_pilot_error(self) -> None:
        """All exceptions inherit from PlanPilotError."""
        assert issubclass(PlanValidationError, PlanPilotError)
        assert issubclass(AuthenticationError, PlanPilotError)
        assert issubclass(ProviderError, PlanPilotError)
        assert issubclass(ProjectURLError, PlanPilotError)
        assert issubclass(SyncError, PlanPilotError)

    def test_plan_validation_error_stores_errors_list(self) -> None:
        """PlanValidationError stores errors list."""
        errors = ["Error 1", "Error 2", "Error 3"]
        exc = PlanValidationError(errors)
        assert exc.errors == errors
        assert len(exc.errors) == 3

    def test_plan_validation_error_formats_message(self) -> None:
        """PlanValidationError formats message."""
        errors = ["Error 1", "Error 2"]
        exc = PlanValidationError(errors)
        message = str(exc)
        assert "Plan validation failed" in message
        assert "Error 1" in message
        assert "Error 2" in message

    def test_plan_validation_error_message_includes_all_errors(self) -> None:
        """PlanValidationError message includes all errors."""
        errors = ["Missing field: id", "Invalid type: title", "Duplicate ID: E-1"]
        exc = PlanValidationError(errors)
        message = str(exc)
        for error in errors:
            assert error in message

    def test_each_exception_can_be_instantiated(self) -> None:
        """Each exception can be instantiated."""
        # PlanValidationError requires errors list
        exc1 = PlanValidationError(["test error"])
        assert isinstance(exc1, PlanPilotError)

        # Other exceptions can be instantiated without arguments
        exc2 = AuthenticationError()
        assert isinstance(exc2, PlanPilotError)

        exc3 = ProviderError()
        assert isinstance(exc3, PlanPilotError)

        exc4 = ProjectURLError()
        assert isinstance(exc4, PlanPilotError)

        exc5 = SyncError()
        assert isinstance(exc5, PlanPilotError)

    def test_exceptions_can_have_custom_messages(self) -> None:
        """Exceptions can have custom messages."""
        exc1 = AuthenticationError("Failed to authenticate")
        assert str(exc1) == "Failed to authenticate"

        exc2 = ProviderError("API call failed")
        assert str(exc2) == "API call failed"

        exc3 = ProjectURLError("Invalid project URL")
        assert str(exc3) == "Invalid project URL"

        exc4 = SyncError("Sync operation failed")
        assert str(exc4) == "Sync operation failed"
