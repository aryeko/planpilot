import httpx
import pytest

from planpilot_v2.providers.github.github_gql import GitHubGraphQLClient


@pytest.mark.asyncio
async def test_github_graphql_client_execute_uses_httpx_transport() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://api.github.com/graphql")
        payload = request.read().decode("utf-8")
        assert "query Test" in payload
        assert '"x": 1' in payload
        return httpx.Response(200, json={"data": {"viewer": {"login": "octocat"}}})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = GitHubGraphQLClient(url="https://api.github.com/graphql", http_client=http_client)
    response = await client.execute("query Test { viewer { login } }", operation_name="Test", variables={"x": 1})
    data = client.get_data(response)

    assert data == {"viewer": {"login": "octocat"}}
    await http_client.aclose()
