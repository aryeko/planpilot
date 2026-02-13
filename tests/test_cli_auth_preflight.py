from __future__ import annotations

import pytest

from planpilot import AuthenticationError
from planpilot.cli import (
    _check_classic_scopes,
    _resolve_init_token,
    _validate_github_auth_for_init,
    _validate_target,
)
from planpilot.engine.progress import SyncProgress


class _FakeResponse:
    def __init__(self, *, status_code: int, headers: dict[str, str] | None = None, payload: dict | None = None) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(
        self,
        *,
        user_response: _FakeResponse,
        repo_response: _FakeResponse,
        graphql_response: _FakeResponse,
        owner_response: _FakeResponse,
    ) -> None:
        self._user_response = user_response
        self._repo_response = repo_response
        self._graphql_response = graphql_response
        self._owner_response = owner_response

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False

    def get(self, url: str, **_kwargs: object) -> _FakeResponse:
        if url.endswith("/user"):
            return self._user_response
        if "/repos/" in url:
            return self._repo_response
        if "/users/" in url:
            return self._owner_response
        raise AssertionError(f"Unexpected GET URL: {url}")

    def post(self, url: str, **_kwargs: object) -> _FakeResponse:
        if url.endswith("/graphql"):
            return self._graphql_response
        raise AssertionError(f"Unexpected POST URL: {url}")


class _SpyProgress(SyncProgress):
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def phase_start(self, phase: str, total: int | None = None) -> None:
        self.events.append(("start", phase))

    def item_done(self, phase: str) -> None:
        self.events.append(("item", phase))

    def phase_done(self, phase: str) -> None:
        self.events.append(("done", phase))

    def phase_error(self, phase: str, error: BaseException) -> None:
        self.events.append(("error", phase))


def test_validate_target_requires_owner_repo_shape() -> None:
    assert _validate_target("owner/repo") is True
    assert _validate_target("owner") == "Use target format owner/repo"
    assert _validate_target("owner/") == "Use target format owner/repo"


def test_check_classic_scopes_allows_absent_or_complete_header() -> None:
    _check_classic_scopes(scopes_header=None)
    _check_classic_scopes(scopes_header="repo, project")


def test_check_classic_scopes_raises_for_missing_scope() -> None:
    with pytest.raises(AuthenticationError, match="missing required GitHub scopes"):
        _check_classic_scopes(scopes_header="repo")


def test_resolve_init_token_supports_all_auth_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("planpilot.cli.asyncio.run", lambda coro: (coro.close(), "resolved")[1])

    assert _resolve_init_token(auth="gh-cli", target="owner/repo", static_token=None) == "resolved"
    assert _resolve_init_token(auth="env", target="owner/repo", static_token=None) == "resolved"
    assert _resolve_init_token(auth="token", target="owner/repo", static_token="abc") == "resolved"


def test_resolve_init_token_rejects_unknown_auth_mode() -> None:
    with pytest.raises(AuthenticationError, match="Unsupported auth mode"):
        _resolve_init_token(auth="unknown", target="owner/repo", static_token=None)


def test_validate_github_auth_for_init_returns_org_owner_type(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeClient(
        user_response=_FakeResponse(status_code=200, headers={"x-oauth-scopes": "repo, project"}),
        repo_response=_FakeResponse(status_code=200),
        graphql_response=_FakeResponse(status_code=200, headers={"content-type": "application/json"}, payload={}),
        owner_response=_FakeResponse(status_code=200, payload={"type": "Organization"}),
    )
    monkeypatch.setattr("planpilot.init.auth.httpx.Client", lambda **_kw: fake)

    assert _validate_github_auth_for_init(token="tok", target="owner/repo") == "org"


def test_validate_github_auth_for_init_emits_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeClient(
        user_response=_FakeResponse(status_code=200, headers={"x-oauth-scopes": "repo, project"}),
        repo_response=_FakeResponse(status_code=200),
        graphql_response=_FakeResponse(status_code=200, headers={"content-type": "application/json"}, payload={}),
        owner_response=_FakeResponse(status_code=200, payload={"type": "Organization"}),
    )
    progress = _SpyProgress()
    monkeypatch.setattr("planpilot.init.auth.httpx.Client", lambda **_kw: fake)

    assert _validate_github_auth_for_init(token="tok", target="owner/repo", progress=progress) == "org"
    starts = [phase for kind, phase in progress.events if kind == "start"]
    assert starts == ["Init Auth", "Init Repo", "Init Projects", "Init Owner"]


def test_validate_github_auth_for_init_scope_failure_emits_phase_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeClient(
        user_response=_FakeResponse(status_code=200, headers={"x-oauth-scopes": "repo"}),
        repo_response=_FakeResponse(status_code=200),
        graphql_response=_FakeResponse(status_code=200, headers={"content-type": "application/json"}, payload={}),
        owner_response=_FakeResponse(status_code=200, payload={"type": "Organization"}),
    )
    progress = _SpyProgress()
    monkeypatch.setattr("planpilot.init.auth.httpx.Client", lambda **_kw: fake)

    with pytest.raises(AuthenticationError, match="missing required GitHub scopes"):
        _validate_github_auth_for_init(token="tok", target="owner/repo", progress=progress)

    assert ("error", "Init Auth") in progress.events


def test_validate_github_auth_for_init_returns_user_owner_type(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeClient(
        user_response=_FakeResponse(status_code=200, headers={"x-oauth-scopes": "repo, project"}),
        repo_response=_FakeResponse(status_code=200),
        graphql_response=_FakeResponse(status_code=200, headers={"content-type": "application/json"}, payload={}),
        owner_response=_FakeResponse(status_code=200, payload={"type": "User"}),
    )
    monkeypatch.setattr("planpilot.init.auth.httpx.Client", lambda **_kw: fake)

    assert _validate_github_auth_for_init(token="tok", target="owner/repo") == "user"


def test_validate_github_auth_for_init_returns_none_on_unknown_owner_type(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeClient(
        user_response=_FakeResponse(status_code=200, headers={"x-oauth-scopes": "repo, project"}),
        repo_response=_FakeResponse(status_code=200),
        graphql_response=_FakeResponse(status_code=200, headers={"content-type": "application/json"}, payload={}),
        owner_response=_FakeResponse(status_code=200, payload={"type": "Bot"}),
    )
    monkeypatch.setattr("planpilot.init.auth.httpx.Client", lambda **_kw: fake)

    assert _validate_github_auth_for_init(token="tok", target="owner/repo") is None


def test_validate_github_auth_for_init_returns_none_on_owner_lookup_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeClient(
        user_response=_FakeResponse(status_code=200, headers={"x-oauth-scopes": "repo, project"}),
        repo_response=_FakeResponse(status_code=200),
        graphql_response=_FakeResponse(status_code=200, headers={"content-type": "application/json"}, payload={}),
        owner_response=_FakeResponse(status_code=404),
    )
    monkeypatch.setattr("planpilot.init.auth.httpx.Client", lambda **_kw: fake)

    assert _validate_github_auth_for_init(token="tok", target="owner/repo") is None


def test_validate_github_auth_for_init_raises_on_auth_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeClient(
        user_response=_FakeResponse(status_code=401),
        repo_response=_FakeResponse(status_code=200),
        graphql_response=_FakeResponse(status_code=200, headers={"content-type": "application/json"}, payload={}),
        owner_response=_FakeResponse(status_code=200, payload={"type": "Organization"}),
    )
    monkeypatch.setattr("planpilot.init.auth.httpx.Client", lambda **_kw: fake)

    with pytest.raises(AuthenticationError, match="authentication failed"):
        _validate_github_auth_for_init(token="tok", target="owner/repo")


def test_validate_github_auth_for_init_auth_failure_emits_phase_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeClient(
        user_response=_FakeResponse(status_code=401),
        repo_response=_FakeResponse(status_code=200),
        graphql_response=_FakeResponse(status_code=200, headers={"content-type": "application/json"}, payload={}),
        owner_response=_FakeResponse(status_code=200, payload={"type": "Organization"}),
    )
    progress = _SpyProgress()
    monkeypatch.setattr("planpilot.init.auth.httpx.Client", lambda **_kw: fake)

    with pytest.raises(AuthenticationError, match="authentication failed"):
        _validate_github_auth_for_init(token="tok", target="owner/repo", progress=progress)

    assert ("error", "Init Auth") in progress.events


def test_validate_github_auth_for_init_raises_on_repo_access_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeClient(
        user_response=_FakeResponse(status_code=200, headers={"x-oauth-scopes": "repo, project"}),
        repo_response=_FakeResponse(status_code=404),
        graphql_response=_FakeResponse(status_code=200, headers={"content-type": "application/json"}, payload={}),
        owner_response=_FakeResponse(status_code=200, payload={"type": "Organization"}),
    )
    monkeypatch.setattr("planpilot.init.auth.httpx.Client", lambda **_kw: fake)

    with pytest.raises(AuthenticationError, match="Cannot access target repository"):
        _validate_github_auth_for_init(token="tok", target="owner/repo")


def test_validate_github_auth_for_init_repo_failure_emits_phase_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeClient(
        user_response=_FakeResponse(status_code=200, headers={"x-oauth-scopes": "repo, project"}),
        repo_response=_FakeResponse(status_code=404),
        graphql_response=_FakeResponse(status_code=200, headers={"content-type": "application/json"}, payload={}),
        owner_response=_FakeResponse(status_code=200, payload={"type": "Organization"}),
    )
    progress = _SpyProgress()
    monkeypatch.setattr("planpilot.init.auth.httpx.Client", lambda **_kw: fake)

    with pytest.raises(AuthenticationError, match="Cannot access target repository"):
        _validate_github_auth_for_init(token="tok", target="owner/repo", progress=progress)

    assert ("error", "Init Repo") in progress.events


def test_validate_github_auth_for_init_raises_on_project_scope_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeClient(
        user_response=_FakeResponse(status_code=200, headers={"x-oauth-scopes": "repo, project"}),
        repo_response=_FakeResponse(status_code=200),
        graphql_response=_FakeResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            payload={"errors": [{"message": "denied"}]},
        ),
        owner_response=_FakeResponse(status_code=200, payload={"type": "Organization"}),
    )
    monkeypatch.setattr("planpilot.init.auth.httpx.Client", lambda **_kw: fake)

    with pytest.raises(AuthenticationError, match="project permissions"):
        _validate_github_auth_for_init(token="tok", target="owner/repo")


def test_validate_github_auth_for_init_projects_failure_emits_phase_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeClient(
        user_response=_FakeResponse(status_code=200, headers={"x-oauth-scopes": "repo, project"}),
        repo_response=_FakeResponse(status_code=200),
        graphql_response=_FakeResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            payload={"errors": [{"message": "denied"}]},
        ),
        owner_response=_FakeResponse(status_code=200, payload={"type": "Organization"}),
    )
    progress = _SpyProgress()
    monkeypatch.setattr("planpilot.init.auth.httpx.Client", lambda **_kw: fake)

    with pytest.raises(AuthenticationError, match="project permissions"):
        _validate_github_auth_for_init(token="tok", target="owner/repo", progress=progress)

    assert ("error", "Init Projects") in progress.events


def test_validate_github_auth_for_init_owner_paths_emit_phase_done(monkeypatch: pytest.MonkeyPatch) -> None:
    progress = _SpyProgress()

    fake_missing_owner = _FakeClient(
        user_response=_FakeResponse(status_code=200, headers={"x-oauth-scopes": "repo, project"}),
        repo_response=_FakeResponse(status_code=200),
        graphql_response=_FakeResponse(status_code=200, headers={"content-type": "application/json"}, payload={}),
        owner_response=_FakeResponse(status_code=404),
    )
    monkeypatch.setattr("planpilot.init.auth.httpx.Client", lambda **_kw: fake_missing_owner)
    assert _validate_github_auth_for_init(token="tok", target="owner/repo", progress=progress) is None

    fake_user_owner = _FakeClient(
        user_response=_FakeResponse(status_code=200, headers={"x-oauth-scopes": "repo, project"}),
        repo_response=_FakeResponse(status_code=200),
        graphql_response=_FakeResponse(status_code=200, headers={"content-type": "application/json"}, payload={}),
        owner_response=_FakeResponse(status_code=200, payload={"type": "User"}),
    )
    monkeypatch.setattr("planpilot.init.auth.httpx.Client", lambda **_kw: fake_user_owner)
    assert _validate_github_auth_for_init(token="tok", target="owner/repo", progress=progress) == "user"

    fake_unknown_owner = _FakeClient(
        user_response=_FakeResponse(status_code=200, headers={"x-oauth-scopes": "repo, project"}),
        repo_response=_FakeResponse(status_code=200),
        graphql_response=_FakeResponse(status_code=200, headers={"content-type": "application/json"}, payload={}),
        owner_response=_FakeResponse(status_code=200, payload={"type": "Bot"}),
    )
    monkeypatch.setattr("planpilot.init.auth.httpx.Client", lambda **_kw: fake_unknown_owner)
    assert _validate_github_auth_for_init(token="tok", target="owner/repo", progress=progress) is None

    owner_done_events = [event for event in progress.events if event == ("done", "Init Owner")]
    assert len(owner_done_events) == 3
