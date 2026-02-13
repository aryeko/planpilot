from __future__ import annotations

from importlib import import_module


def test_sdk_ops_modules_export_expected_functions() -> None:
    sync_ops = import_module("planpilot.sdk_ops.sync_ops")
    map_sync_ops = import_module("planpilot.sdk_ops.map_sync_ops")
    clean_ops = import_module("planpilot.sdk_ops.clean_ops")
    persistence_ops = import_module("planpilot.sdk_ops.persistence")

    assert callable(sync_ops.run_sync)
    assert callable(map_sync_ops.discover_remote_plan_ids)
    assert callable(map_sync_ops.run_map_sync)
    assert callable(clean_ops.run_clean)
    assert callable(clean_ops.discover_and_delete_items)
    assert callable(persistence_ops.persist_sync_map)
    assert callable(persistence_ops.output_sync_path)
    assert callable(persistence_ops.load_sync_map)
