"""Core configuration loading exports."""

from planpilot.core.config.loader import load_config
from planpilot.core.config.scaffold import (
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
    "load_config",
    "scaffold_config",
    "write_config",
]
