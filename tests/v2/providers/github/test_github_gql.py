import pytest

from planpilot_v2.providers.github.github_gql import GitHubGraphQLClient


@pytest.mark.asyncio
async def test_github_graphql_client_execute_delegates_to_caller() -> None:
    async def caller(query: str, variables: dict[str, object]) -> dict[str, object]:
        assert query == "query { viewer { login } }"
        assert variables == {"x": 1}
        return {"viewer": {"login": "octocat"}}

    client = GitHubGraphQLClient(caller)
    payload = await client.execute("query { viewer { login } }", {"x": 1})

    assert payload == {"viewer": {"login": "octocat"}}
