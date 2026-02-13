"""Tests for the scaffold module (detect_target, detect_plan_paths, scaffold_config)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from planpilot.config.scaffold import (
    create_plan_stubs,
    detect_plan_paths,
    detect_target,
    scaffold_config,
    write_config,
)
from planpilot.contracts.config import PlanPaths
from planpilot.contracts.exceptions import ConfigError

# ---------------------------------------------------------------------------
# detect_target
# ---------------------------------------------------------------------------


def _mock_run(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


class TestDetectTarget:
    def test_ssh_remote(self) -> None:
        with patch(
            "planpilot.config.scaffold.subprocess.run",
            return_value=_mock_run("git@github.com:owner/repo.git\n"),
        ):
            assert detect_target() == "owner/repo"

    def test_https_remote(self) -> None:
        with patch(
            "planpilot.config.scaffold.subprocess.run", return_value=_mock_run("https://github.com/owner/repo.git\n")
        ):
            assert detect_target() == "owner/repo"

    def test_https_remote_without_dot_git(self) -> None:
        with patch(
            "planpilot.config.scaffold.subprocess.run", return_value=_mock_run("https://github.com/owner/repo\n")
        ):
            assert detect_target() == "owner/repo"

    def test_ssh_remote_without_dot_git(self) -> None:
        with patch("planpilot.config.scaffold.subprocess.run", return_value=_mock_run("git@github.com:owner/repo\n")):
            assert detect_target() == "owner/repo"

    def test_non_zero_return_code(self) -> None:
        with patch("planpilot.config.scaffold.subprocess.run", return_value=_mock_run("", returncode=128)):
            assert detect_target() is None

    def test_unparseable_remote(self) -> None:
        with patch("planpilot.config.scaffold.subprocess.run", return_value=_mock_run("file:///local/path\n")):
            assert detect_target() is None

    def test_subprocess_exception(self) -> None:
        with patch("planpilot.config.scaffold.subprocess.run", side_effect=FileNotFoundError("git not found")):
            assert detect_target() is None

    def test_timeout_exception(self) -> None:
        with patch(
            "planpilot.config.scaffold.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="git", timeout=5),
        ):
            assert detect_target() is None


# ---------------------------------------------------------------------------
# detect_plan_paths
# ---------------------------------------------------------------------------


class TestDetectPlanPaths:
    def test_split_files_in_dot_plans(self, tmp_path: Path) -> None:
        plans = tmp_path / ".plans"
        plans.mkdir()
        (plans / "epics.json").write_text("[]")
        (plans / "stories.json").write_text("[]")
        (plans / "tasks.json").write_text("[]")

        result = detect_plan_paths(tmp_path)

        assert result is not None
        assert result.epics == Path(".plans/epics.json")
        assert result.stories == Path(".plans/stories.json")
        assert result.tasks == Path(".plans/tasks.json")
        assert result.unified is None

    def test_unified_file_in_plans(self, tmp_path: Path) -> None:
        plans = tmp_path / "plans"
        plans.mkdir()
        (plans / "plan.json").write_text("{}")

        result = detect_plan_paths(tmp_path)

        assert result is not None
        assert result.unified == Path("plans/plan.json")
        assert result.epics is None

    def test_split_preferred_over_unified(self, tmp_path: Path) -> None:
        plans = tmp_path / ".plans"
        plans.mkdir()
        (plans / "epics.json").write_text("[]")
        (plans / "stories.json").write_text("[]")
        (plans / "tasks.json").write_text("[]")
        (plans / "plan.json").write_text("{}")

        result = detect_plan_paths(tmp_path)

        assert result is not None
        assert result.epics is not None
        assert result.unified is None

    def test_partial_split_files_returns_none(self, tmp_path: Path) -> None:
        plans = tmp_path / ".plans"
        plans.mkdir()
        (plans / "epics.json").write_text("[]")
        # Missing stories.json and tasks.json

        assert detect_plan_paths(tmp_path) is None

    def test_empty_directory_returns_none(self, tmp_path: Path) -> None:
        assert detect_plan_paths(tmp_path) is None

    def test_no_plan_dirs_returns_none(self, tmp_path: Path) -> None:
        (tmp_path / "something_else").mkdir()
        assert detect_plan_paths(tmp_path) is None

    def test_defaults_to_cwd(self) -> None:
        # Should not raise regardless of what cwd looks like.
        result = detect_plan_paths()
        assert result is None or isinstance(result, PlanPaths)

    def test_iterdir_error_returns_none(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        plans = tmp_path / ".plans"
        plans.mkdir()

        original_iterdir = Path.iterdir

        def _patched_iterdir(self: Path):
            if self == plans:
                raise OSError("permission denied")
            return original_iterdir(self)

        monkeypatch.setattr(Path, "iterdir", _patched_iterdir)

        assert detect_plan_paths(tmp_path) is None


# ---------------------------------------------------------------------------
# scaffold_config
# ---------------------------------------------------------------------------


class TestScaffoldConfig:
    def test_minimal_config(self) -> None:
        config = scaffold_config(target="owner/repo", board_url="https://github.com/orgs/owner/projects/1")

        assert config["provider"] == "github"
        assert config["target"] == "owner/repo"
        assert config["board_url"] == "https://github.com/orgs/owner/projects/1"
        assert "plan_paths" in config
        # Defaults should be omitted
        assert "auth" not in config
        assert "validation_mode" not in config
        assert "label" not in config
        assert "max_concurrent" not in config

    def test_non_default_values_included(self) -> None:
        config = scaffold_config(
            target="owner/repo",
            board_url="https://github.com/orgs/owner/projects/1",
            auth="env",
            validation_mode="partial",
            label="custom-label",
            max_concurrent=5,
        )

        assert config["auth"] == "env"
        assert config["validation_mode"] == "partial"
        assert config["label"] == "custom-label"
        assert config["max_concurrent"] == 5

    def test_custom_plan_paths(self) -> None:
        config = scaffold_config(
            target="owner/repo",
            board_url="https://github.com/orgs/owner/projects/1",
            plan_paths={"unified": "plan.json"},
        )

        assert config["plan_paths"] == {"unified": "plan.json"}

    def test_invalid_config_raises_config_error(self) -> None:
        with pytest.raises(ConfigError, match="invalid config"):
            scaffold_config(
                target="owner/repo",
                board_url="https://github.com/orgs/owner/projects/1",
                auth="token",  # token auth requires a non-empty token
            )

    def test_field_config_included(self) -> None:
        config = scaffold_config(
            target="owner/repo",
            board_url="https://github.com/orgs/owner/projects/1",
            field_config={"status": "Todo"},
        )

        assert config["field_config"] == {"status": "Todo"}

    def test_user_board_defaults_create_type_strategy_to_label(self) -> None:
        config = scaffold_config(
            target="owner/repo",
            board_url="https://github.com/users/alice/projects/1",
        )

        assert config["field_config"]["create_type_strategy"] == "label"

    def test_user_board_rejects_issue_type_strategy(self) -> None:
        with pytest.raises(ConfigError, match="create_type_strategy"):
            scaffold_config(
                target="owner/repo",
                board_url="https://github.com/users/alice/projects/1",
                field_config={"create_type_strategy": "issue-type"},
            )

    def test_invalid_board_url_raises_config_error(self) -> None:
        with pytest.raises(ConfigError, match="Unsupported project URL"):
            scaffold_config(
                target="owner/repo",
                board_url="https://github.com/orgs/owner/projects/",
            )

    def test_token_auth_with_token_included(self) -> None:
        config = scaffold_config(
            target="owner/repo",
            board_url="https://github.com/orgs/owner/projects/1",
            auth="token",
            token="ghp_example",
        )

        assert config["auth"] == "token"
        assert config["token"] == "ghp_example"

    def test_user_board_accepts_explicit_label_strategy(self) -> None:
        config = scaffold_config(
            target="owner/repo",
            board_url="https://github.com/users/alice/projects/1",
            field_config={"create_type_strategy": "label"},
        )

        assert config["field_config"]["create_type_strategy"] == "label"

    def test_non_github_provider_skips_project_url_parsing(self) -> None:
        config = scaffold_config(
            provider="jira",
            target="owner/repo",
            board_url="not-a-github-url",
            plan_paths={"unified": "plan.json"},
        )

        assert config["provider"] == "jira"


# ---------------------------------------------------------------------------
# write_config
# ---------------------------------------------------------------------------


class TestWriteConfig:
    def test_writes_json(self, tmp_path: Path) -> None:
        config = {"provider": "github", "target": "owner/repo"}
        output = tmp_path / "planpilot.json"

        write_config(config, output)

        assert output.exists()
        loaded = json.loads(output.read_text())
        assert loaded == config

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        output = tmp_path / "nested" / "dir" / "planpilot.json"

        write_config({"key": "val"}, output)

        assert output.exists()


# ---------------------------------------------------------------------------
# create_plan_stubs
# ---------------------------------------------------------------------------


class TestCreatePlanStubs:
    def test_creates_split_files(self, tmp_path: Path) -> None:
        paths = {"epics": ".plans/epics.json", "stories": ".plans/stories.json", "tasks": ".plans/tasks.json"}

        created = create_plan_stubs(paths, base=tmp_path)

        assert len(created) == 3
        for rel in paths.values():
            full = tmp_path / rel
            assert full.exists()
            assert json.loads(full.read_text()) == []

    def test_creates_unified_file(self, tmp_path: Path) -> None:
        paths = {"unified": ".plans/plan.json"}

        created = create_plan_stubs(paths, base=tmp_path)

        assert len(created) == 1
        content = json.loads((tmp_path / ".plans/plan.json").read_text())
        assert content == {"items": []}

    def test_skips_existing_files(self, tmp_path: Path) -> None:
        plans = tmp_path / ".plans"
        plans.mkdir()
        existing = plans / "epics.json"
        existing.write_text('[{"id": "E1"}]')

        paths = {"epics": ".plans/epics.json", "stories": ".plans/stories.json"}

        created = create_plan_stubs(paths, base=tmp_path)

        assert len(created) == 1  # Only stories.json created
        assert json.loads(existing.read_text()) == [{"id": "E1"}]  # Not overwritten
