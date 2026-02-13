import pytest

from planpilot.core.contracts.exceptions import ProviderCapabilityError
from planpilot.core.contracts.plan import PlanItemType
from planpilot.core.providers.github.item import GitHubItem
from planpilot.core.providers.github.models import GitHubProviderContext


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
        self.parent_remove_calls: list[tuple[str, str]] = []
        self.dep_remove_calls: list[tuple[str, str]] = []
        self.current_parent_id: str | None = None
        self.current_blocker_ids: set[str] = set()

    async def add_sub_issue(self, child_issue_id: str, parent_issue_id: str) -> None:
        self.parent_calls.append((child_issue_id, parent_issue_id))

    async def add_blocked_by(self, blocked_issue_id: str, blocker_issue_id: str) -> None:
        self.dep_calls.append((blocked_issue_id, blocker_issue_id))

    async def remove_sub_issue(self, child_issue_id: str, parent_issue_id: str) -> None:
        self.parent_remove_calls.append((child_issue_id, parent_issue_id))

    async def remove_blocked_by(self, blocked_issue_id: str, blocker_issue_id: str) -> None:
        self.dep_remove_calls.append((blocked_issue_id, blocker_issue_id))

    async def get_relations(self, *, issue_id: str) -> tuple[str | None, set[str]]:
        _ = issue_id
        return self.current_parent_id, set(self.current_blocker_ids)


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


@pytest.mark.asyncio
async def test_reconcile_relations_removes_stale_and_adds_missing() -> None:
    provider = _StubProvider()
    provider.current_parent_id = "I-old-parent"
    provider.current_blocker_ids = {"I-old-blocker", "I-keep"}

    parent = GitHubItem(
        provider=provider,
        issue_id="I-parent",
        number=1,
        title="P",
        body="",
        item_type=PlanItemType.EPIC,
        url="u",
    )
    keep_blocker = GitHubItem(
        provider=provider,
        issue_id="I-keep",
        number=2,
        title="Keep",
        body="",
        item_type=PlanItemType.TASK,
        url="u",
    )
    new_blocker = GitHubItem(
        provider=provider,
        issue_id="I-new",
        number=3,
        title="New",
        body="",
        item_type=PlanItemType.TASK,
        url="u",
    )
    child = GitHubItem(
        provider=provider,
        issue_id="I-child",
        number=4,
        title="C",
        body="",
        item_type=PlanItemType.STORY,
        url="u",
    )

    await child.reconcile_relations(parent=parent, blockers=[keep_blocker, new_blocker])

    assert provider.parent_remove_calls == [("I-child", "I-old-parent")]
    assert provider.parent_calls == [("I-child", "I-parent")]
    assert provider.dep_remove_calls == [("I-child", "I-old-blocker")]
    assert provider.dep_calls == [("I-child", "I-new")]


@pytest.mark.asyncio
async def test_reconcile_relations_raises_when_sub_issues_capability_missing() -> None:
    provider = _StubProvider(supports_sub_issues=False)
    parent = GitHubItem(
        provider=provider,
        issue_id="I-parent",
        number=1,
        title="P",
        body="",
        item_type=PlanItemType.EPIC,
        url="u",
    )
    child = GitHubItem(
        provider=provider,
        issue_id="I-child",
        number=2,
        title="C",
        body="",
        item_type=PlanItemType.STORY,
        url="u",
    )

    with pytest.raises(ProviderCapabilityError, match="sub-issues"):
        await child.reconcile_relations(parent=parent, blockers=[])


@pytest.mark.asyncio
async def test_reconcile_relations_raises_when_blocked_by_capability_missing() -> None:
    provider = _StubProvider(supports_blocked_by=False)
    blocker = GitHubItem(
        provider=provider,
        issue_id="I-blocker",
        number=1,
        title="B",
        body="",
        item_type=PlanItemType.TASK,
        url="u",
    )
    child = GitHubItem(
        provider=provider,
        issue_id="I-child",
        number=2,
        title="C",
        body="",
        item_type=PlanItemType.STORY,
        url="u",
    )

    with pytest.raises(ProviderCapabilityError, match="blocked-by"):
        await child.reconcile_relations(parent=None, blockers=[blocker])


@pytest.mark.asyncio
async def test_reconcile_relations_noop_when_state_already_matches() -> None:
    provider = _StubProvider()
    provider.current_parent_id = "I-parent"
    provider.current_blocker_ids = {"I-blocker"}
    parent = GitHubItem(
        provider=provider,
        issue_id="I-parent",
        number=1,
        title="P",
        body="",
        item_type=PlanItemType.EPIC,
        url="u",
    )
    blocker = GitHubItem(
        provider=provider,
        issue_id="I-blocker",
        number=2,
        title="B",
        body="",
        item_type=PlanItemType.TASK,
        url="u",
    )
    child = GitHubItem(
        provider=provider,
        issue_id="I-child",
        number=3,
        title="C",
        body="",
        item_type=PlanItemType.STORY,
        url="u",
    )

    await child.reconcile_relations(parent=parent, blockers=[blocker])

    assert provider.parent_remove_calls == []
    assert provider.parent_calls == []
    assert provider.dep_remove_calls == []
    assert provider.dep_calls == []
