from planpilot.providers.base import ProviderContext
from planpilot.providers.github.models import GitHubProviderContext, ResolvedField


def test_resolved_field_and_context_defaults() -> None:
    field = ResolvedField(id="f1", name="Status", kind="single_select", options=[{"id": "o1", "name": "Backlog"}])
    context = GitHubProviderContext(
        repo_id="repo1",
        label_id="label1",
        issue_type_ids={"EPIC": "it1"},
        project_owner_type="org",
    )

    assert isinstance(context, ProviderContext)
    assert field.name == "Status"
    assert context.project_id is None
    assert context.supports_sub_issues is False
    assert context.create_type_strategy == "issue-type"
