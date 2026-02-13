from planpilot.core.contracts.exceptions import (
    AuthenticationError,
    ConfigError,
    CreateItemPartialFailureError,
    PlanLoadError,
    PlanPilotError,
    PlanValidationError,
    ProjectURLError,
    ProviderCapabilityError,
    ProviderError,
    SyncError,
)


def test_exception_hierarchy() -> None:
    assert issubclass(ConfigError, PlanPilotError)
    assert issubclass(PlanLoadError, PlanPilotError)
    assert issubclass(PlanValidationError, PlanPilotError)
    assert issubclass(ProviderError, PlanPilotError)
    assert issubclass(AuthenticationError, ProviderError)
    assert issubclass(ProjectURLError, ProviderError)
    assert issubclass(ProviderCapabilityError, ProviderError)
    assert issubclass(CreateItemPartialFailureError, ProviderError)
    assert issubclass(SyncError, PlanPilotError)


def test_provider_capability_error_exposes_capability() -> None:
    err = ProviderCapabilityError("missing capability", capability="set_parent")

    assert err.capability == "set_parent"


def test_create_item_partial_failure_error_fields() -> None:
    err = CreateItemPartialFailureError(
        "partial failure",
        created_item_id="node-1",
        created_item_key="#1",
        created_item_url="https://example/items/1",
        completed_steps=("create_issue",),
        retryable=True,
    )

    assert err.created_item_id == "node-1"
    assert err.created_item_key == "#1"
    assert err.created_item_url == "https://example/items/1"
    assert err.completed_steps == ("create_issue",)
    assert err.retryable is True
