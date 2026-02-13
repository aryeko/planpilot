from __future__ import annotations

from importlib import import_module


def test_cli_parser_module_exports_public_build_parser() -> None:
    parser_module = import_module("planpilot.cli.parser")
    cli_module = import_module("planpilot.cli")

    assert parser_module.build_parser is cli_module.build_parser


def test_cli_app_module_exports_public_main() -> None:
    app_module = import_module("planpilot.cli.app")
    cli_module = import_module("planpilot.cli")

    assert app_module.main is cli_module.main


def test_cli_command_modules_export_summary_formatters() -> None:
    cli_module = import_module("planpilot.cli")
    sync_module = import_module("planpilot.cli.commands.sync")
    clean_module = import_module("planpilot.cli.commands.clean")
    map_sync_module = import_module("planpilot.cli.commands.map_sync")

    assert sync_module.format_sync_summary is cli_module._format_summary
    assert clean_module.format_clean_summary is cli_module._format_clean_summary
    assert map_sync_module.format_map_sync_summary is cli_module._format_map_sync_summary
