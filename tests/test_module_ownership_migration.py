from __future__ import annotations

import ast
from importlib import import_module
from pathlib import Path


def test_legacy_metadata_module_is_compatibility_shim() -> None:
    legacy_module = import_module("planpilot.metadata")
    new_module = import_module("planpilot.core.metadata")

    assert legacy_module.parse_metadata_block is new_module.parse_metadata_block


def test_legacy_progress_module_is_compatibility_shim() -> None:
    legacy_module = import_module("planpilot.progress")
    new_module = import_module("planpilot.cli.progress.rich")

    assert legacy_module.RichSyncProgress is new_module.RichSyncProgress


def test_legacy_config_scaffold_module_is_compatibility_shim() -> None:
    legacy_module = import_module("planpilot.config.scaffold")
    new_module = import_module("planpilot.cli.scaffold.config_builder")

    assert callable(legacy_module.detect_target)
    assert callable(new_module.detect_target)
    assert callable(legacy_module.detect_plan_paths)
    assert callable(new_module.detect_plan_paths)
    assert callable(legacy_module.scaffold_config)
    assert callable(new_module.scaffold_config)
    assert callable(legacy_module.write_config)
    assert callable(new_module.write_config)
    assert callable(legacy_module.create_plan_stubs)
    assert callable(new_module.create_plan_stubs)


def test_legacy_init_validation_module_is_compatibility_shim() -> None:
    legacy_module = import_module("planpilot.init.validation")
    new_module = import_module("planpilot.cli.init.validation")

    valid = "https://github.com/orgs/acme/projects/1"
    invalid = "https://example.com/not-a-project"
    assert legacy_module.validate_board_url(valid) is True
    assert new_module.validate_board_url(valid) is True
    assert legacy_module.validate_board_url(invalid) is False
    assert new_module.validate_board_url(invalid) is False


def test_legacy_init_auth_module_is_compatibility_shim() -> None:
    legacy_module = import_module("planpilot.init.auth")
    new_module = import_module("planpilot.core.auth.preflight")

    assert legacy_module.resolve_init_token is new_module.resolve_init_token
    assert legacy_module.validate_github_auth_for_init is new_module.validate_github_auth_for_init


def test_legacy_map_sync_package_is_compatibility_shim() -> None:
    legacy_module = import_module("planpilot.map_sync")
    new_module = import_module("planpilot.core.map_sync")

    assert legacy_module.MapSyncReconciler is new_module.MapSyncReconciler
    assert legacy_module.RemotePlanParser is new_module.RemotePlanParser
    assert legacy_module.RemotePlanPersistence is new_module.RemotePlanPersistence


def test_legacy_persistence_package_is_compatibility_shim() -> None:
    legacy_sync_module = import_module("planpilot.persistence.sync_map")
    legacy_remote_plan_module = import_module("planpilot.persistence.remote_plan")
    new_sync_module = import_module("planpilot.cli.persistence.sync_map")
    new_remote_plan_module = import_module("planpilot.cli.persistence.remote_plan")

    assert callable(legacy_sync_module.persist_sync_map)
    assert callable(new_sync_module.persist_sync_map)
    assert callable(legacy_sync_module.load_sync_map)
    assert callable(new_sync_module.load_sync_map)
    assert callable(legacy_sync_module.output_sync_path)
    assert callable(new_sync_module.output_sync_path)
    assert callable(legacy_remote_plan_module.persist_plan_from_remote)
    assert callable(new_remote_plan_module.persist_plan_from_remote)


def test_legacy_targets_module_is_compatibility_shim() -> None:
    legacy_module = import_module("planpilot.targets.github_project")
    new_module = import_module("planpilot.cli.scaffold.targets.github_project")

    url = "https://github.com/orgs/acme/projects/7"
    assert legacy_module.parse_project_url(url) == ("org", "acme", 7)
    assert new_module.parse_project_url(url) == ("org", "acme", 7)


def test_sdk_imports_core_modules_for_owned_domains() -> None:
    sdk_path = Path(__file__).resolve().parents[1] / "src" / "planpilot" / "sdk.py"
    module = ast.parse(sdk_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module for node in ast.walk(module) if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert "planpilot.core.metadata" in imported_modules
    assert "planpilot.core.map_sync" in imported_modules
    assert "planpilot.core.clean" in imported_modules
    assert "planpilot.core.contracts" in imported_modules
    assert "planpilot.core.engine" in imported_modules
    assert "planpilot.core.plan" in imported_modules
    assert "planpilot.core.providers" in imported_modules
    assert "planpilot.core.renderers" in imported_modules


def test_cli_commands_use_cli_owned_progress_and_persistence_helpers() -> None:
    root = Path(__file__).resolve().parents[1]
    files = {
        root / "src" / "planpilot" / "cli" / "commands" / "sync.py": {
            "planpilot.cli.progress.rich",
            "planpilot.cli.persistence.sync_map",
        },
        root / "src" / "planpilot" / "cli" / "commands" / "map_sync.py": {
            "planpilot.cli.progress.rich",
            "planpilot.cli.persistence.sync_map",
            "planpilot.cli.persistence.remote_plan",
        },
    }

    missing: list[str] = []
    for file_path, expected_imports in files.items():
        module = ast.parse(file_path.read_text(encoding="utf-8"))
        imported_modules = {
            node.module for node in ast.walk(module) if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        for expected_import in expected_imports:
            if expected_import not in imported_modules:
                missing.append(f"{file_path}: missing import from {expected_import}")

    assert not missing, f"cli commands should use cli-owned helpers: {missing}"


def test_core_github_gql_wrappers_are_importable() -> None:
    legacy_client_module = import_module("planpilot.providers.github.github_gql.client")
    core_client_module = import_module("planpilot.core.providers.github.github_gql.client")
    legacy_exceptions_module = import_module("planpilot.providers.github.github_gql.exceptions")
    core_exceptions_module = import_module("planpilot.core.providers.github.github_gql.exceptions")

    assert core_client_module.GitHubGraphQLClient is legacy_client_module.GitHubGraphQLClient
    assert core_exceptions_module.GraphQLClientError is legacy_exceptions_module.GraphQLClientError
