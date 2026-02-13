from __future__ import annotations

import ast
from pathlib import Path


def test_cli_imports_only_public_planpilot_api() -> None:
    cli_path = Path(__file__).resolve().parents[1] / "src" / "planpilot" / "cli.py"
    module = ast.parse(cli_path.read_text(encoding="utf-8"))

    forbidden_prefixes = (
        "planpilot.engine",
        "planpilot.providers",
        "planpilot.auth",
        "planpilot.contracts",
    )
    violations: list[str] = []

    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name.startswith(forbidden_prefixes):
                    violations.append(name)
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            if node.module.startswith(forbidden_prefixes):
                violations.append(node.module)

    assert not violations, f"cli.py imports forbidden internal modules: {sorted(set(violations))}"
