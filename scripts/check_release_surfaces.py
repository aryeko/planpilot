#!/usr/bin/env python3
"""Check that plugin, marketplace, and runtime-pin release surfaces stay in sync."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

SEMVER_PATTERN = r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
PLANPILOT_PIN_RE = re.compile(rf"planpilot==(?P<version>{SEMVER_PATTERN})")
PLANPILOT_OUTPUT_RE = re.compile(rf"planpilot (?P<version>{SEMVER_PATTERN})")

RUNTIME_PIN_FILES = (
    Path("skills/plan-sync/SKILL.md"),
    Path("skills/INSTALL.md"),
    Path("skills/INSTALL.agent.md"),
    Path("README.md"),
    Path("RELEASE.md"),
    Path("docs/guides/plugin-skills-guide.md"),
    Path("docs/reference/plugin-reference.md"),
)

PROHIBITED_WRAPPER_TEXT = (
    "bundled wrapper",
    "plugin wrapper",
    ".claude-plugin/bin/planpilot",
    "CLAUDE_PLUGIN_ROOT",
)

OBSOLETE_PATHS = (
    Path(".claude-plugin/bin"),
    Path("src/planpilot/.claude-plugin"),
)


def read_project_version(repo_root: Path) -> str:
    with (repo_root / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    version = pyproject["tool"]["poetry"]["version"]
    if not isinstance(version, str) or not version:
        raise ValueError("pyproject.toml tool.poetry.version must be a non-empty string")
    return version


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def ensure_directory(repo_root: Path, relative_path: Path) -> list[str]:
    path = repo_root / relative_path
    if path.is_dir() and not path.is_symlink():
        return []
    return [f"{relative_path} must be a real directory"]


def ensure_absent(repo_root: Path, relative_path: Path, *, fix: bool) -> list[str]:
    path = repo_root / relative_path
    if not path.exists() and not path.is_symlink():
        return []
    if fix:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
        return []
    return [f"{relative_path} is obsolete and must be removed"]


def update_json_surface(
    repo_root: Path,
    relative_path: Path,
    version: str,
    updater: Callable[[dict[str, Any], str], list[str]],
    *,
    fix: bool,
) -> list[str]:
    path = repo_root / relative_path
    payload = load_json(path)
    errors = updater(payload, version)
    if not errors:
        return []
    if fix:
        write_json(path, payload)
        return update_json_surface(repo_root, relative_path, version, updater, fix=False)
    return [f"{relative_path}: {error}" for error in errors]


def update_claude_plugin(payload: dict[str, Any], version: str) -> list[str]:
    errors: list[str] = []
    if payload.get("version") != version:
        errors.append(f"version must be {version}")
        payload["version"] = version
    if payload.get("skills") != "./skills/":
        errors.append("skills must be ./skills/")
        payload["skills"] = "./skills/"
    if payload.get("commands") != "./commands/":
        errors.append("commands must be ./commands/")
        payload["commands"] = "./commands/"
    if "hooks" in payload:
        errors.append("hooks must be removed")
        payload.pop("hooks", None)
    unsupported = sorted(set(payload).intersection({"category", "tags"}))
    if unsupported:
        errors.append(f"Claude plugin contains marketplace-only fields: {', '.join(unsupported)}")
        for key in unsupported:
            payload.pop(key, None)
    return errors


def update_claude_marketplace(payload: dict[str, Any], version: str) -> list[str]:
    plugin = get_plugin_entry(payload)
    errors: list[str] = []
    if not payload.get("description"):
        errors.append("marketplace description must be set")
        payload["description"] = (
            "Agent planning plugins for PRDs, technical specs, and GitHub Issues + Projects v2 sync."
        )
    if plugin.get("version") != version:
        errors.append(f"plugin version must be {version}")
        plugin["version"] = version
    if plugin.get("source") != "./":
        errors.append("plugin source must be ./")
        plugin["source"] = "./"
    return errors


def update_codex_plugin(payload: dict[str, Any], version: str) -> list[str]:
    errors: list[str] = []
    if payload.get("version") != version:
        errors.append(f"version must be {version}")
        payload["version"] = version
    if payload.get("skills") != "./skills/":
        errors.append("skills must be ./skills/")
        payload["skills"] = "./skills/"
    forbidden = sorted(set(payload).intersection({"commands", "hooks"}))
    if forbidden:
        errors.append(f"Codex plugin contains forbidden fields: {', '.join(forbidden)}")
        for key in forbidden:
            payload.pop(key, None)
    interface = payload.get("interface")
    if not isinstance(interface, dict):
        errors.append("Codex plugin interface must be an object")
    else:
        default_prompt = interface.get("defaultPrompt")
        if not isinstance(default_prompt, list) or not default_prompt:
            errors.append("Codex plugin interface.defaultPrompt must be a non-empty list")
        elif len(default_prompt) > 3:
            errors.append("Codex plugin interface.defaultPrompt must contain at most 3 prompts")
        else:
            for index, prompt in enumerate(default_prompt):
                if not isinstance(prompt, str) or not prompt.strip():
                    errors.append(f"Codex plugin interface.defaultPrompt[{index}] must be a non-empty string")
                elif len(prompt) > 128:
                    errors.append(f"Codex plugin interface.defaultPrompt[{index}] must be at most 128 characters")
    return errors


def update_codex_marketplace(payload: dict[str, Any], version: str) -> list[str]:
    plugin = get_plugin_entry(payload)
    errors: list[str] = []
    if plugin.get("version") != version:
        errors.append(f"plugin version must be {version}")
        plugin["version"] = version
    expected_source = {"source": "local", "path": "./"}
    if plugin.get("source") != expected_source:
        errors.append('plugin source must be {"source": "local", "path": "./"}')
        plugin["source"] = expected_source
    expected_policy = {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}
    if plugin.get("policy") != expected_policy:
        errors.append("plugin policy must be AVAILABLE/ON_INSTALL")
        plugin["policy"] = expected_policy
    if plugin.get("category") != "Productivity":
        errors.append("plugin category must be Productivity")
        plugin["category"] = "Productivity"
    return errors


def get_plugin_entry(payload: dict[str, Any]) -> dict[str, Any]:
    plugins = payload.get("plugins")
    if not isinstance(plugins, list):
        raise ValueError("marketplace plugins must be a list")
    matches = [entry for entry in plugins if isinstance(entry, dict) and entry.get("name") == "planpilot"]
    if len(matches) != 1:
        raise ValueError("marketplace must contain exactly one planpilot plugin entry")
    return matches[0]


def ensure_runtime_pin(repo_root: Path, relative_path: Path, version: str, *, fix: bool) -> list[str]:
    path = repo_root / relative_path
    text = path.read_text(encoding="utf-8")
    matches = list(PLANPILOT_PIN_RE.finditer(text))
    output_matches = list(PLANPILOT_OUTPUT_RE.finditer(text))
    errors: list[str] = []
    if not matches:
        errors.append(f"{relative_path} must contain planpilot=={version}")
    elif any(match.group("version") != version for match in matches):
        errors.append(f"{relative_path} planpilot runtime pin must be {version}")
    if any(match.group("version") != version for match in output_matches):
        errors.append(f"{relative_path} planpilot version output examples must be {version}")

    for phrase in PROHIBITED_WRAPPER_TEXT:
        if phrase in text:
            errors.append(f"{relative_path} must not reference {phrase}")

    if errors and fix and (matches or output_matches):
        updated_text = PLANPILOT_PIN_RE.sub(f"planpilot=={version}", text)
        updated_text = PLANPILOT_OUTPUT_RE.sub(f"planpilot {version}", updated_text)
        path.write_text(updated_text, encoding="utf-8")
        return ensure_runtime_pin(repo_root, relative_path, version, fix=False)
    return errors


def check_release_surfaces(repo_root: Path, fix: bool = False) -> list[str]:
    repo_root = repo_root.resolve()
    version = read_project_version(repo_root)
    errors: list[str] = []

    errors.extend(ensure_directory(repo_root, Path("skills")))
    errors.extend(ensure_directory(repo_root, Path("commands")))
    for obsolete_path in OBSOLETE_PATHS:
        errors.extend(ensure_absent(repo_root, obsolete_path, fix=fix))

    json_surfaces: tuple[tuple[Path, Callable[[dict[str, Any], str], list[str]]], ...] = (
        (Path(".claude-plugin/plugin.json"), update_claude_plugin),
        (Path(".claude-plugin/marketplace.json"), update_claude_marketplace),
        (Path(".codex-plugin/plugin.json"), update_codex_plugin),
        (Path(".agents/plugins/marketplace.json"), update_codex_marketplace),
    )
    for relative_path, updater in json_surfaces:
        errors.extend(update_json_surface(repo_root, relative_path, version, updater, fix=fix))

    for relative_path in RUNTIME_PIN_FILES:
        errors.extend(ensure_runtime_pin(repo_root, relative_path, version, fix=fix))

    if fix and errors:
        return check_release_surfaces(repo_root, fix=False)
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix", action="store_true", help="Rewrite supported drift to match pyproject.toml")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root to inspect")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors = check_release_surfaces(args.repo_root, fix=args.fix)
    if errors:
        print("Release surface check failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Release surfaces are in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
