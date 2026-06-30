from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def load_release_surfaces_module() -> object:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_release_surfaces.py"
    spec = importlib.util.spec_from_file_location("check_release_surfaces", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_surfaces_are_in_sync() -> None:
    module = load_release_surfaces_module()
    repo_root = Path(__file__).resolve().parents[1]

    errors = module.check_release_surfaces(repo_root, fix=False)

    assert errors == []


def test_fix_mode_preserves_unfixable_codex_manifest_errors(tmp_path: Path) -> None:
    module = load_release_surfaces_module()
    repo_root = tmp_path
    version = "2.5.0"

    (repo_root / "pyproject.toml").write_text(
        f'[tool.poetry]\nname = "planpilot"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    (repo_root / "skills").mkdir()
    (repo_root / "commands").mkdir()

    for relative_path in module.RUNTIME_PIN_FILES:
        path = repo_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"uvx --from planpilot=={version} planpilot\n", encoding="utf-8")

    write_json(repo_root / ".claude-plugin/plugin.json", {"name": "planpilot", "version": version})
    write_json(
        repo_root / ".claude-plugin/marketplace.json",
        {"plugins": [{"name": "planpilot", "version": version, "source": "./"}]},
    )
    write_json(repo_root / ".codex-plugin/plugin.json", {"name": "planpilot", "version": version})
    write_json(
        repo_root / ".agents/plugins/marketplace.json",
        {
            "plugins": [
                {
                    "name": "planpilot",
                    "version": version,
                    "source": {"source": "local", "path": "./"},
                    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    "category": "Productivity",
                }
            ]
        },
    )

    errors = module.check_release_surfaces(repo_root, fix=True)

    assert ".codex-plugin/plugin.json: Codex plugin interface must be an object" in errors


def test_fix_mode_updates_runtime_output_examples(tmp_path: Path) -> None:
    module = load_release_surfaces_module()
    repo_root = tmp_path
    version = "2.5.0"
    create_minimal_release_surface(repo_root, version)
    plan_sync = repo_root / "skills/plan-sync/SKILL.md"
    plan_sync.write_text(
        "uvx --from planpilot==2.4.9 planpilot --version\nexpected output: planpilot 2.4.9\n",
        encoding="utf-8",
    )

    errors = module.check_release_surfaces(repo_root, fix=True)

    assert errors == []
    assert plan_sync.read_text(encoding="utf-8") == (
        "uvx --from planpilot==2.5.0 planpilot --version\nexpected output: planpilot 2.5.0\n"
    )


def create_minimal_release_surface(repo_root: Path, version: str) -> None:
    (repo_root / "pyproject.toml").write_text(
        f'[tool.poetry]\nname = "planpilot"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    (repo_root / "skills").mkdir()
    (repo_root / "commands").mkdir()

    module = load_release_surfaces_module()
    for relative_path in module.RUNTIME_PIN_FILES:
        path = repo_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"uvx --from planpilot=={version} planpilot\n", encoding="utf-8")

    write_json(
        repo_root / ".claude-plugin/plugin.json",
        {"name": "planpilot", "version": version, "skills": "./skills/", "commands": "./commands/"},
    )
    write_json(
        repo_root / ".claude-plugin/marketplace.json",
        {
            "description": "Planpilot marketplace",
            "plugins": [{"name": "planpilot", "version": version, "source": "./"}],
        },
    )
    write_json(
        repo_root / ".codex-plugin/plugin.json",
        {
            "name": "planpilot",
            "version": version,
            "skills": "./skills/",
            "interface": {"defaultPrompt": ["Use planpilot."]},
        },
    )
    write_json(
        repo_root / ".agents/plugins/marketplace.json",
        {
            "plugins": [
                {
                    "name": "planpilot",
                    "version": version,
                    "source": {"source": "local", "path": "./"},
                    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    "category": "Productivity",
                }
            ]
        },
    )


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
