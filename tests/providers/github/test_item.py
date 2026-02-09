import pytest

from planpilot.contracts.exceptions import ProviderCapabilityError
from planpilot.contracts.plan import PlanItemType
from planpilot.providers.github.item import GitHubItem
from planpilot.providers.github.models import GitHubProviderContext


class _StubProvider:
    def __init__(self, *, supports_sub_issues: bool = True, supports_blocked_by: bool = True) -> None:
        self.context = GitHubProviderContext(
            repo_id="r",
            label_id="l",
            issue_type_ids={},
            project_owner_type="org",
            supports_sub_issues=supports_sub_issues,
            supports_blocked_by=supports_blocked_by,
        )
        self.parent_calls: list[tuple[str, str]] = []
        self.dep_calls: list[tuple[str, str]] = []

    async def add_sub_issue(self, child_issue_id: str, parent_issue_id: str) -> None:
        self.parent_calls.append((child_issue_id, parent_issue_id))

    async def add_blocked_by(self, blocked_issue_id: str, blocker_issue_id: str) -> None:
        self.dep_calls.append((blocked_issue_id, blocker_issue_id))


@pytest.mark.asyncio
async def test_set_parent_delegates_when_supported() -> None:
    provider = _StubProvider()
    parent = GitHubItem(
        provider=provider, issue_id="I1", number=1, title="P", body="", item_type=PlanItemType.EPIC, url="u"
    )
    child = GitHubItem(
        provider=provider, issue_id="I2", number=2, title="C", body="", item_type=PlanItemType.STORY, url="u"
    )

    await child.set_parent(parent)

    assert provider.parent_calls == [("I2", "I1")]
    assert child.key == "#2"
    assert child.url == "u"
    assert child.body == ""
    assert child.item_type == PlanItemType.STORY


@pytest.mark.asyncio
async def test_set_parent_raises_when_capability_missing() -> None:
    provider = _StubProvider(supports_sub_issues=False)
    parent = GitHubItem(
        provider=provider, issue_id="I1", number=1, title="P", body="", item_type=PlanItemType.EPIC, url="u"
    )
    child = GitHubItem(
        provider=provider, issue_id="I2", number=2, title="C", body="", item_type=PlanItemType.STORY, url="u"
    )

    with pytest.raises(ProviderCapabilityError, match="sub-issues"):
        await child.set_parent(parent)


@pytest.mark.asyncio
async def test_add_dependency_delegates_when_supported() -> None:
    provider = _StubProvider()
    blocker = GitHubItem(
        provider=provider, issue_id="I1", number=1, title="B", body="", item_type=PlanItemType.TASK, url="u"
    )
    blocked = GitHubItem(
        provider=provider, issue_id="I2", number=2, title="T", body="", item_type=PlanItemType.TASK, url="u"
    )

    await blocked.add_dependency(blocker)

    assert provider.dep_calls == [("I2", "I1")]


@pytest.mark.asyncio
async def test_add_dependency_raises_when_capability_missing() -> None:
    provider = _StubProvider(supports_blocked_by=False)
    blocker = GitHubItem(
        provider=provider, issue_id="I1", number=1, title="B", body="", item_type=PlanItemType.TASK, url="u"
    )
    blocked = GitHubItem(
        provider=provider, issue_id="I2", number=2, title="T", body="", item_type=PlanItemType.TASK, url="u"
    )

    with pytest.raises(ProviderCapabilityError, match="blocked-by"):
        await blocked.add_dependency(blocker)
