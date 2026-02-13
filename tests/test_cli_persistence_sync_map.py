from __future__ import annotations

import json
from pathlib import Path

import pytest

from planpilot import ConfigError, SyncError, SyncMap
from planpilot.cli.persistence.sync_map import load_sync_map, output_sync_path, persist_sync_map


def test_output_sync_path_uses_dry_run_suffix_when_enabled(tmp_path: Path) -> None:
    sync_path = tmp_path / "sync-map.json"
    assert output_sync_path(sync_path=sync_path, dry_run=False) == sync_path
    assert output_sync_path(sync_path=sync_path, dry_run=True) == Path(f"{sync_path}.dry-run")


def test_persist_sync_map_writes_json_payload(tmp_path: Path) -> None:
    sync_path = tmp_path / "nested" / "sync-map.json"
    sync_map = SyncMap(
        plan_id="p1",
        target="owner/repo",
        board_url="https://github.com/orgs/acme/projects/1",
        entries={},
    )

    persist_sync_map(sync_map=sync_map, sync_path=sync_path, dry_run=False)

    assert sync_path.exists()
    persisted = json.loads(sync_path.read_text(encoding="utf-8"))
    assert persisted["plan_id"] == "p1"


def test_persist_sync_map_raises_sync_error_on_write_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sync_path = tmp_path / "sync-map.json"
    sync_map = SyncMap(
        plan_id="p1",
        target="owner/repo",
        board_url="https://github.com/orgs/acme/projects/1",
        entries={},
    )
    original_write_text = Path.write_text

    def _boom(self: Path, data: str, *, encoding: str | None = None) -> int:
        if self == sync_path:
            raise OSError("disk full")
        return original_write_text(self, data, encoding=encoding)

    monkeypatch.setattr(Path, "write_text", _boom)

    with pytest.raises(SyncError, match="failed to persist sync map"):
        persist_sync_map(sync_map=sync_map, sync_path=sync_path, dry_run=False)


def test_load_sync_map_returns_default_when_file_missing(tmp_path: Path) -> None:
    sync_map = load_sync_map(
        sync_path=tmp_path / "missing.json",
        plan_id="p1",
        target="owner/repo",
        board_url="https://github.com/orgs/acme/projects/1",
    )

    assert sync_map.plan_id == "p1"
    assert sync_map.entries == {}


def test_load_sync_map_reads_existing_file(tmp_path: Path) -> None:
    sync_path = tmp_path / "sync-map.json"
    sync_path.write_text(
        json.dumps(
            {
                "plan_id": "p1",
                "target": "owner/repo",
                "board_url": "https://github.com/orgs/acme/projects/1",
                "entries": {},
            }
        ),
        encoding="utf-8",
    )

    loaded = load_sync_map(
        sync_path=sync_path,
        plan_id="ignored",
        target="ignored",
        board_url="ignored",
    )

    assert loaded.plan_id == "p1"


@pytest.mark.parametrize("payload", ["{bad-json", "{}"])
def test_load_sync_map_raises_config_error_for_invalid_payload(tmp_path: Path, payload: str) -> None:
    sync_path = tmp_path / "sync-map.json"
    sync_path.write_text(payload, encoding="utf-8")

    with pytest.raises(ConfigError, match="invalid sync map file"):
        load_sync_map(
            sync_path=sync_path,
            plan_id="p1",
            target="owner/repo",
            board_url="https://github.com/orgs/acme/projects/1",
        )
