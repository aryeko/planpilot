from __future__ import annotations

import ast
from pathlib import Path


def _collect_python_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.rglob("*.py") if path.is_file())


def _find_forbidden_imports(files: list[Path], forbidden_prefixes: tuple[str, ...]) -> list[str]:
    violations: list[str] = []
    for path in files:
        module = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(forbidden_prefixes):
                        violations.append(f"{path}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                if node.module.startswith(forbidden_prefixes):
                    violations.append(f"{path}: from {node.module} import ...")
    return violations


def test_map_sync_does_not_import_engine_internals() -> None:
    root = Path(__file__).resolve().parents[1]
    files = _collect_python_files(root / "src" / "planpilot" / "map_sync")
    violations = _find_forbidden_imports(files, ("planpilot.engine",))
    assert not violations, f"map_sync imports forbidden engine internals: {violations}"


def test_config_and_init_do_not_import_provider_internals() -> None:
    root = Path(__file__).resolve().parents[1]
    config_files = _collect_python_files(root / "src" / "planpilot" / "config")
    init_files = _collect_python_files(root / "src" / "planpilot" / "init")
    files = config_files + init_files
    violations = _find_forbidden_imports(files, ("planpilot.providers",))
    assert not violations, f"config/init import forbidden provider internals: {violations}"


def test_sdk_does_not_import_github_provider_internals() -> None:
    root = Path(__file__).resolve().parents[1]
    files = [root / "src" / "planpilot" / "sdk.py"]
    violations = _find_forbidden_imports(files, ("planpilot.providers.github",))
    assert not violations, f"sdk imports forbidden github provider internals: {violations}"


def test_sdk_does_not_import_cli_layer() -> None:
    root = Path(__file__).resolve().parents[1]
    files = [root / "src" / "planpilot" / "sdk.py"]
    violations = _find_forbidden_imports(files, ("planpilot.cli",))
    assert not violations, f"sdk imports forbidden cli layer modules: {violations}"


def test_cli_sync_commands_import_persistence_helpers() -> None:
    root = Path(__file__).resolve().parents[1]
    required_modules = {
        root / "src" / "planpilot" / "cli" / "commands" / "sync.py": {
            "planpilot.cli.persistence.sync_map",
        },
        root / "src" / "planpilot" / "cli" / "commands" / "map_sync.py": {
            "planpilot.cli.persistence.sync_map",
            "planpilot.cli.persistence.remote_plan",
        },
    }
    missing: list[str] = []

    for path, expected_imports in required_modules.items():
        module = ast.parse(path.read_text(encoding="utf-8"))
        imported_modules = {
            node.module for node in ast.walk(module) if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        for expected_import in expected_imports:
            if expected_import not in imported_modules:
                missing.append(f"{path}: missing import from {expected_import}")

    assert not missing, f"cli sync commands must import persistence helpers: {missing}"


def test_github_ops_do_not_import_cli_sdk_or_engine_layers() -> None:
    root = Path(__file__).resolve().parents[1]
    files = _collect_python_files(root / "src" / "planpilot" / "providers" / "github" / "ops")
    violations = _find_forbidden_imports(
        files,
        (
            "planpilot.cli",
            "planpilot.sdk",
            "planpilot.engine",
        ),
    )
    assert not violations, f"github ops import forbidden higher layers: {violations}"


def test_core_github_modules_do_not_import_legacy_generated_client_paths() -> None:
    root = Path(__file__).resolve().parents[1]
    core_github_dir = root / "src" / "planpilot" / "core" / "providers" / "github"
    files = [path for path in _collect_python_files(core_github_dir) if "github_gql" not in path.parts]
    violations = _find_forbidden_imports(files, ("planpilot.providers.github.github_gql",))
    assert not violations, f"core github modules import legacy generated client paths: {violations}"


def test_cli_owned_modules_do_not_import_legacy_paths() -> None:
    root = Path(__file__).resolve().parents[1]
    files = [
        root / "src" / "planpilot" / "cli" / "persistence" / "sync_map.py",
        root / "src" / "planpilot" / "cli" / "persistence" / "remote_plan.py",
        root / "src" / "planpilot" / "cli" / "scaffold" / "config_builder.py",
        root / "src" / "planpilot" / "cli" / "scaffold" / "targets" / "github_project.py",
        root / "src" / "planpilot" / "cli" / "init" / "validation.py",
    ]
    violations = _find_forbidden_imports(
        files,
        (
            "planpilot.persistence",
            "planpilot.config.scaffold",
            "planpilot.targets.github_project",
            "planpilot.init.validation",
        ),
    )
    assert not violations, f"cli-owned modules import legacy paths: {violations}"
