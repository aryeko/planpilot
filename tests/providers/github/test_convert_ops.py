from __future__ import annotations

from types import SimpleNamespace

import pytest

from planpilot.core.contracts.exceptions import ProviderError
from planpilot.core.providers.github.ops.convert import item_from_issue_core, split_target


def test_item_from_issue_core_handles_missing_labels() -> None:
    issue = SimpleNamespace(
        id="I1",
        number=1,
        url="https://github.com/acme/repo/issues/1",
        title="Issue",
        body="text",
        labels=None,
    )

    item = item_from_issue_core(provider=object(), issue=issue)

    assert item.labels == []


def test_split_target_parses_owner_and_repo() -> None:
    owner, repo = split_target("acme/planpilot")
    assert owner == "acme"
    assert repo == "planpilot"


@pytest.mark.parametrize("target", ["acme", "/repo", "owner/", ""])
def test_split_target_rejects_invalid_targets(target: str) -> None:
    with pytest.raises(ProviderError, match="Expected owner/repo"):
        split_target(target)


def test_item_from_issue_core_ignores_invalid_item_type_metadata() -> None:
    issue = SimpleNamespace(
        id="I1",
        number=1,
        url="https://github.com/acme/repo/issues/1",
        title="Issue",
        body="\n".join(["PLANPILOT_META_V1", "ITEM_TYPE:NOT_A_TYPE", "END_PLANPILOT_META"]),
        labels=None,
    )

    item = item_from_issue_core(provider=object(), issue=issue)

    assert item.item_type is None
