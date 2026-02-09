from pathlib import Path

import pytest
from pydantic import ValidationError

from planpilot.contracts.config import PlanPaths, PlanPilotConfig


def test_plan_paths_requires_one_input_path() -> None:
    with pytest.raises(ValidationError):
        PlanPaths()


def test_plan_paths_unified_cannot_mix_with_split_files() -> None:
    with pytest.raises(ValidationError):
        PlanPaths(unified=Path("plan.json"), epics=Path("epics.json"))


def test_planpilot_config_auth_token_combinations() -> None:
    PlanPilotConfig(
        provider="github",
        target="owner/repo",
        auth="gh-cli",
        token=None,
        board_url="https://github.com/orgs/owner/projects/1",
        plan_paths=PlanPaths(unified=Path("plan.json")),
    )

    PlanPilotConfig(
        provider="github",
        target="owner/repo",
        auth="env",
        token=None,
        board_url="https://github.com/orgs/owner/projects/1",
        plan_paths=PlanPaths(unified=Path("plan.json")),
    )

    PlanPilotConfig(
        provider="github",
        target="owner/repo",
        auth="token",
        token="abc123",
        board_url="https://github.com/orgs/owner/projects/1",
        plan_paths=PlanPaths(unified=Path("plan.json")),
    )

    with pytest.raises(ValidationError):
        PlanPilotConfig(
            provider="github",
            target="owner/repo",
            auth="token",
            token=None,
            board_url="https://github.com/orgs/owner/projects/1",
            plan_paths=PlanPaths(unified=Path("plan.json")),
        )

    with pytest.raises(ValidationError):
        PlanPilotConfig(
            provider="github",
            target="owner/repo",
            auth="gh-cli",
            token="abc123",
            board_url="https://github.com/orgs/owner/projects/1",
            plan_paths=PlanPaths(unified=Path("plan.json")),
        )


def test_planpilot_config_rejects_unknown_auth_mode() -> None:
    with pytest.raises(ValidationError):
        PlanPilotConfig(
            provider="github",
            target="owner/repo",
            auth="invalid-mode",
            token=None,
            board_url="https://github.com/orgs/owner/projects/1",
            plan_paths=PlanPaths(unified=Path("plan.json")),
        )


def test_planpilot_config_is_frozen() -> None:
    config = PlanPilotConfig(
        provider="github",
        target="owner/repo",
        board_url="https://github.com/orgs/owner/projects/1",
        plan_paths=PlanPaths(unified=Path("plan.json")),
    )

    with pytest.raises(ValidationError):
        config.label = "new-label"
