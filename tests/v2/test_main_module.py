"""Tests for the planpilot_v2 module entrypoint."""

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
    """`planpilot_v2.__main__` should only exit when executed as __main__."""
    cli_module = types.ModuleType("planpilot_v2.cli")
    call_count = {"value": 0}

    def fake_main() -> int:
        call_count["value"] += 1
        return 7

    cli_module.main = fake_main
    monkeypatch.setitem(sys.modules, "planpilot_v2.cli", cli_module)
    monkeypatch.delitem(sys.modules, "planpilot_v2.__main__", raising=False)

    importlib.import_module("planpilot_v2.__main__")
    assert call_count["value"] == 0

    monkeypatch.delitem(sys.modules, "planpilot_v2.__main__", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("planpilot_v2.__main__", run_name="__main__")

    assert call_count["value"] == 1
    assert exc_info.value.code == 7


def test_pyproject_defines_planpilot_v2_script_alias() -> None:
    """Poetry script alias should expose the v2 CLI entrypoint."""
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    pyproject_data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    scripts = pyproject_data["tool"]["poetry"]["scripts"]
    assert scripts["planpilot_v2"] == "planpilot_v2.cli:main"
