"""CLI scaffold helpers."""

from planpilot.cli.scaffold.config_builder import (
    create_plan_stubs,
    detect_plan_paths,
    detect_target,
    scaffold_config,
    write_config,
)

__all__ = [
    "create_plan_stubs",
    "detect_plan_paths",
    "detect_target",
    "scaffold_config",
    "write_config",
]
