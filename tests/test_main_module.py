"""Tests for the planpilot module entrypoint."""

from __future__ import annotations

import importlib
import runpy
import sys
import tomllib
import types
from pathlib import Path

import pytest


def test_module_entrypoint_guarded_on_import_and_exits_when_run_as_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`planpilot.__main__` should only exit when executed as __main__."""
    cli_module = types.ModuleType("planpilot.cli")
    call_count = {"value": 0}

    def fake_main() -> int:
        call_count["value"] += 1
        return 7

    cli_module.main = fake_main  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "planpilot.cli", cli_module)
    monkeypatch.delitem(sys.modules, "planpilot.__main__", raising=False)

    importlib.import_module("planpilot.__main__")
    assert call_count["value"] == 0

    monkeypatch.delitem(sys.modules, "planpilot.__main__", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("planpilot.__main__", run_name="__main__")

    assert call_count["value"] == 1
    assert exc_info.value.code == 7


def test_pyproject_defines_planpilot_script_alias() -> None:
    """Poetry script alias should expose the CLI entrypoint."""
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    pyproject_data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    scripts = pyproject_data["tool"]["poetry"]["scripts"]
    assert scripts["planpilot"] == "planpilot.cli:main"


def test_cli_package_entrypoint_exits_when_run_as_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """`python -m planpilot.cli` should dispatch through `planpilot.cli.main`."""
    cli_module = importlib.import_module("planpilot.cli")
    call_count = {"value": 0}

    def fake_main() -> int:
        call_count["value"] += 1
        return 9

    monkeypatch.setattr(cli_module, "main", fake_main)

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("planpilot.cli", run_name="__main__")

    assert call_count["value"] == 1
    assert exc_info.value.code == 9
