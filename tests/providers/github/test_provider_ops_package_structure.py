from __future__ import annotations

from importlib import import_module


def test_provider_ops_modules_export_expected_functions() -> None:
    crud_ops = import_module("planpilot.core.providers.github.ops.crud")
    relations_ops = import_module("planpilot.core.providers.github.ops.relations")
    labels_ops = import_module("planpilot.core.providers.github.ops.labels")
    project_ops = import_module("planpilot.core.providers.github.ops.project")
    convert_ops = import_module("planpilot.core.providers.github.ops.convert")

    assert callable(crud_ops.search_issue_nodes)
    assert callable(crud_ops.create_issue)
    assert callable(crud_ops.update_issue)
    assert callable(crud_ops.get_issue)
    assert callable(crud_ops.get_item_labels)
    assert callable(relations_ops.is_duplicate_relation_error)
    assert callable(labels_ops.ensure_discovery_labels)
    assert callable(project_ops.ensure_project_item)
    assert callable(project_ops.ensure_project_fields)
    assert callable(convert_ops.item_from_issue_core)
    assert callable(convert_ops.split_target)
