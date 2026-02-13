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


def test_sdk_ops_do_not_import_github_provider_internals() -> None:
    root = Path(__file__).resolve().parents[1]
    files = _collect_python_files(root / "src" / "planpilot" / "sdk_ops")
    violations = _find_forbidden_imports(files, ("planpilot.providers.github",))
    assert not violations, f"sdk_ops import forbidden github provider internals: {violations}"


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
