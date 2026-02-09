import pytest

from planpilot_v2.contracts.config import FieldConfig
from planpilot_v2.contracts.exceptions import CreateItemPartialFailureError
from planpilot_v2.contracts.item import CreateItemInput, ItemSearchFilters, UpdateItemInput
from planpilot_v2.contracts.plan import PlanItemType
from planpilot_v2.providers.github.models import GitHubProviderContext
from planpilot_v2.providers.github.provider import GitHubProvider


@pytest.mark.asyncio
async def test_aenter_builds_context(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = GitHubProvider(
        target="acme/repo",
        token="token",
        board_url="https://github.com/orgs/acme/projects/1",
        label="planpilot",
        field_config=FieldConfig(),
    )

    async def fake_enter_transport() -> None:
        return None

    async def fake_resolve_repo() -> tuple[str, str, dict[str, str]]:
        return "repo-id", "label-id", {"EPIC": "type-1"}

    async def fake_resolve_project() -> tuple[str, str, int, str | None]:
        return "org", "acme", 1, "project-id"

    monkeypatch.setattr(provider, "_open_transport", fake_enter_transport)
    monkeypatch.setattr(provider, "_resolve_repo_context", fake_resolve_repo)
    monkeypatch.setattr(provider, "_resolve_project_context", fake_resolve_project)

    entered = await provider.__aenter__()

    assert entered is provider
    assert provider.context.repo_id == "repo-id"
    assert provider.context.project_id == "project-id"


@pytest.mark.asyncio
async def test_create_item_happy_path_issue_type_strategy(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = GitHubProvider(
        target="acme/repo",
        token="token",
        board_url="https://github.com/orgs/acme/projects/1",
        label="planpilot",
        field_config=FieldConfig(create_type_strategy="issue-type"),
    )
    provider.context = GitHubProviderContext(
        repo_id="repo-id",
        label_id="label-id",
        issue_type_ids={"TASK": "task-type"},
        project_owner_type="org",
        project_id="project-id",
        supports_issue_type=True,
        create_type_strategy="issue-type",
        create_type_map={"TASK": "Task"},
        size_field_id="size-id",
        size_options=[{"id": "opt-s", "name": "S"}],
    )

    calls: list[str] = []

    async def fake_create_issue(input: CreateItemInput) -> dict[str, object]:
        calls.append("issue_created")
        return {
            "id": "I1",
            "number": 42,
            "url": "https://github.com/acme/repo/issues/42",
            "title": input.title,
            "body": input.body,
        }

    async def fake_issue_type(issue_id: str, item_type: PlanItemType) -> None:
        calls.append("issue_type_set")

    async def fake_discovery(issue_id: str, labels: list[str]) -> None:
        calls.append("labels_set")

    async def fake_project(issue_id: str) -> str:
        calls.append("project_item_added")
        return "PVTI_1"

    async def fake_fields(project_item_id: str, input: CreateItemInput) -> None:
        calls.append("project_fields_set")

    monkeypatch.setattr(provider, "_create_issue", fake_create_issue)
    monkeypatch.setattr(provider, "_ensure_issue_type", fake_issue_type)
    monkeypatch.setattr(provider, "_ensure_discovery_labels", fake_discovery)
    monkeypatch.setattr(provider, "_ensure_project_item", fake_project)
    monkeypatch.setattr(provider, "_ensure_project_fields", fake_fields)

    created = await provider.create_item(
        CreateItemInput(title="T", body="B", item_type=PlanItemType.TASK, labels=["planpilot"], size="S")
    )

    assert created.id == "I1"
    assert calls == ["issue_created", "issue_type_set", "labels_set", "project_item_added", "project_fields_set"]


@pytest.mark.asyncio
async def test_create_item_raises_partial_failure_after_issue_created(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = GitHubProvider(
        target="acme/repo",
        token="token",
        board_url="https://github.com/orgs/acme/projects/1",
        label="planpilot",
        field_config=FieldConfig(create_type_strategy="label"),
    )
    provider.context = GitHubProviderContext(
        repo_id="repo-id",
        label_id="label-id",
        issue_type_ids={},
        project_owner_type="org",
        create_type_strategy="label",
        create_type_map={"TASK": "type:task"},
    )

    async def fake_create_issue(input: CreateItemInput) -> dict[str, object]:
        return {
            "id": "I1",
            "number": 42,
            "url": "https://github.com/acme/repo/issues/42",
            "title": input.title,
            "body": input.body,
        }

    async def fake_type_label(issue_id: str, item_type: PlanItemType) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(provider, "_create_issue", fake_create_issue)
    monkeypatch.setattr(provider, "_ensure_type_label", fake_type_label)

    with pytest.raises(CreateItemPartialFailureError) as excinfo:
        await provider.create_item(CreateItemInput(title="T", body="B", item_type=PlanItemType.TASK))

    assert excinfo.value.created_item_id == "I1"
    assert excinfo.value.completed_steps == ("issue_created",)


@pytest.mark.asyncio
async def test_update_item_uses_update_issue(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = GitHubProvider(
        target="acme/repo",
        token="token",
        board_url="https://github.com/orgs/acme/projects/1",
        label="planpilot",
        field_config=FieldConfig(),
    )
    provider.context = GitHubProviderContext(
        repo_id="repo-id", label_id="label-id", issue_type_ids={}, project_owner_type="org"
    )

    async def fake_get_item(item_id: str):
        return await provider._item_from_node(
            {"id": item_id, "number": 2, "url": "u", "title": "old", "body": "old", "labels": {"nodes": []}}
        )

    async def fake_update_issue(item_id: str, update_input: UpdateItemInput) -> dict[str, object]:
        return {
            "id": item_id,
            "number": 2,
            "url": "u",
            "title": update_input.title or "old",
            "body": update_input.body or "old",
            "labels": {"nodes": []},
        }

    monkeypatch.setattr(provider, "get_item", fake_get_item)
    monkeypatch.setattr(provider, "_update_issue", fake_update_issue)

    updated = await provider.update_item("I1", UpdateItemInput(title="new"))
    assert updated.title == "new"


@pytest.mark.asyncio
async def test_search_items_applies_labels_and_body_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = GitHubProvider(
        target="acme/repo",
        token="token",
        board_url="https://github.com/orgs/acme/projects/1",
        label="planpilot",
        field_config=FieldConfig(),
    )
    provider.context = GitHubProviderContext(
        repo_id="repo-id", label_id="label-id", issue_type_ids={}, project_owner_type="org"
    )

    captured: dict[str, str] = {}

    async def fake_search(query: str) -> list[dict[str, object]]:
        captured["query"] = query
        return [{"id": "I1", "number": 1, "url": "u", "title": "t", "body": "PLAN_ID:abc", "labels": {"nodes": []}}]

    monkeypatch.setattr(provider, "_search_issue_nodes", fake_search)

    items = await provider.search_items(ItemSearchFilters(labels=["planpilot", "foo"], body_contains="PLAN_ID:abc"))

    assert len(items) == 1
    assert "label:planpilot" in captured["query"]
    assert "label:foo" in captured["query"]
    assert "PLAN_ID:abc" in captured["query"]


@pytest.mark.asyncio
async def test_search_items_without_body_contains(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = GitHubProvider(
        target="acme/repo",
        token="token",
        board_url="https://github.com/orgs/acme/projects/1",
        label="planpilot",
        field_config=FieldConfig(),
    )
    provider.context = GitHubProviderContext(
        repo_id="repo-id", label_id="label-id", issue_type_ids={}, project_owner_type="org"
    )

    captured: dict[str, str] = {}

    async def fake_search(query: str) -> list[dict[str, object]]:
        captured["query"] = query
        return [{"id": "I1", "number": 1, "url": "u", "title": "t", "body": "", "labels": {"nodes": []}}]

    monkeypatch.setattr(provider, "_search_issue_nodes", fake_search)

    await provider.search_items(ItemSearchFilters(labels=["planpilot"]))
    assert "label:planpilot" in captured["query"]
    assert "PLAN_ID:" not in captured["query"]


@pytest.mark.asyncio
async def test_create_item_raises_original_error_when_issue_not_created(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = GitHubProvider(
        target="acme/repo",
        token="token",
        board_url="https://github.com/orgs/acme/projects/1",
        label="planpilot",
        field_config=FieldConfig(),
    )
    provider.context = GitHubProviderContext(
        repo_id="repo-id", label_id="label-id", issue_type_ids={}, project_owner_type="org"
    )

    async def fake_create_issue(input: CreateItemInput) -> dict[str, object]:
        raise RuntimeError("create boom")

    monkeypatch.setattr(provider, "_create_issue", fake_create_issue)

    with pytest.raises(RuntimeError, match="create boom"):
        await provider.create_item(CreateItemInput(title="T", body="B", item_type=PlanItemType.TASK))


@pytest.mark.asyncio
async def test_update_item_applies_optional_mutations(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = GitHubProvider(
        target="acme/repo",
        token="token",
        board_url="https://github.com/orgs/acme/projects/1",
        label="planpilot",
        field_config=FieldConfig(),
    )
    provider.context = GitHubProviderContext(
        repo_id="repo-id",
        label_id="label-id",
        issue_type_ids={},
        project_owner_type="org",
        project_id="P1",
        create_type_strategy="label",
    )

    async def fake_get_item(item_id: str):
        return await provider._item_from_node(
            {"id": item_id, "number": 2, "url": "u", "title": "old", "body": "old", "labels": {"nodes": []}}
        )

    async def fake_get_labels(item_id: str) -> list[str]:
        return ["existing"]

    async def fake_update_issue(item_id: str, update_input: UpdateItemInput) -> dict[str, object]:
        return {
            "id": item_id,
            "number": 2,
            "url": "u",
            "title": update_input.title or "old",
            "body": update_input.body or "old",
            "labels": {"nodes": []},
        }

    called: list[str] = []

    async def fake_type_label(item_id: str, item_type: PlanItemType) -> None:
        called.append("type_label")

    async def fake_discovery(item_id: str, labels: list[str]) -> None:
        called.append("discovery")

    async def fake_project_item(item_id: str) -> str:
        called.append("project")
        return "PVTI_1"

    async def fake_project_fields(project_item_id: str, create_input: CreateItemInput) -> None:
        called.append("fields")

    monkeypatch.setattr(provider, "get_item", fake_get_item)
    monkeypatch.setattr(provider, "_get_item_labels", fake_get_labels)
    monkeypatch.setattr(provider, "_update_issue", fake_update_issue)
    monkeypatch.setattr(provider, "_ensure_type_label", fake_type_label)
    monkeypatch.setattr(provider, "_ensure_discovery_labels", fake_discovery)
    monkeypatch.setattr(provider, "_ensure_project_item", fake_project_item)
    monkeypatch.setattr(provider, "_ensure_project_fields", fake_project_fields)

    updated = await provider.update_item(
        "I1",
        UpdateItemInput(
            title="new",
            item_type=PlanItemType.TASK,
            labels=["planpilot"],
            size="S",
        ),
    )

    assert updated.title == "new"
    assert called == ["type_label", "discovery", "project", "fields"]


@pytest.mark.asyncio
async def test_update_item_issue_type_strategy_uses_issue_type_hook(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = GitHubProvider(
        target="acme/repo",
        token="token",
        board_url="https://github.com/orgs/acme/projects/1",
        label="planpilot",
        field_config=FieldConfig(create_type_strategy="issue-type"),
    )
    provider.context = GitHubProviderContext(
        repo_id="repo-id",
        label_id="label-id",
        issue_type_ids={"TASK": "task-id"},
        project_owner_type="org",
        create_type_strategy="issue-type",
    )

    async def fake_get_item(item_id: str):
        return await provider._item_from_node(
            {"id": item_id, "number": 2, "url": "u", "title": "old", "body": "old", "labels": {"nodes": []}}
        )

    async def fake_update_issue(item_id: str, update_input: UpdateItemInput) -> dict[str, object]:
        return {"id": item_id, "number": 2, "url": "u", "title": "new", "body": "old", "labels": {"nodes": []}}

    called: list[str] = []

    async def fake_issue_type(item_id: str, item_type: PlanItemType) -> None:
        called.append(f"{item_id}:{item_type.value}")

    monkeypatch.setattr(provider, "get_item", fake_get_item)
    monkeypatch.setattr(provider, "_update_issue", fake_update_issue)
    monkeypatch.setattr(provider, "_ensure_issue_type", fake_issue_type)

    await provider.update_item("I1", UpdateItemInput(title="new", item_type=PlanItemType.TASK))

    assert called == ["I1:TASK"]


def test_resolve_create_type_policy_user_falls_back_to_label() -> None:
    provider = GitHubProvider(
        target="acme/repo",
        token="token",
        board_url="https://github.com/users/acme/projects/1",
        label="planpilot",
        field_config=FieldConfig(create_type_strategy="issue-type"),
    )

    strategy, mapping = provider._resolve_create_type_policy("user")
    assert strategy == "label"
    assert mapping["EPIC"] == "Epic"
