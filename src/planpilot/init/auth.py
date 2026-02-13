"""Init auth resolution and provider-access validation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine

import httpx

from planpilot.auth.base import TokenResolver
from planpilot.auth.resolvers.env import EnvTokenResolver
from planpilot.auth.resolvers.gh_cli import GhCliTokenResolver
from planpilot.auth.resolvers.static import StaticTokenResolver
from planpilot.contracts.exceptions import AuthenticationError
from planpilot.contracts.init import InitProgress

_REQUIRED_CLASSIC_SCOPES = {"repo", "project"}


class InitTokenResolverFactory:
    @staticmethod
    def create(*, auth: str, static_token: str | None) -> TokenResolver:
        if auth == "gh-cli":
            return GhCliTokenResolver(hostname="github.com")
        if auth == "env":
            return EnvTokenResolver()
        if auth == "token":
            return StaticTokenResolver(token=static_token or "")
        raise AuthenticationError(f"Unsupported auth mode: {auth}")


class InitAuthService:
    def __init__(self, *, client_factory: Callable[[], httpx.Client] | None = None) -> None:
        self._client_factory = client_factory or (lambda: httpx.Client(timeout=10.0))

    def resolve_token(
        self,
        *,
        auth: str,
        static_token: str | None,
        run_async: Callable[[Coroutine[object, object, str]], str] | None = None,
    ) -> str:
        resolver = InitTokenResolverFactory.create(auth=auth, static_token=static_token)
        runner = run_async or asyncio.run
        return runner(resolver.resolve())

    def validate_github_auth_for_init(
        self,
        *,
        token: str,
        target: str,
        progress: InitProgress | None = None,
    ) -> str | None:
        owner, repo = target.split("/", 1)
        with self._client_factory() as client:
            if progress is not None:
                progress.phase_start("Init Auth")
            user_resp = client.get("https://api.github.com/user", headers=_github_headers(token))
            if user_resp.status_code != 200:
                auth_error = AuthenticationError(
                    "GitHub authentication failed; verify your token/gh login and network access"
                )
                if progress is not None:
                    progress.phase_error("Init Auth", auth_error)
                raise auth_error
            try:
                _check_classic_scopes(scopes_header=user_resp.headers.get("x-oauth-scopes"))
            except AuthenticationError as error:
                if progress is not None:
                    progress.phase_error("Init Auth", error)
                raise
            if progress is not None:
                progress.phase_done("Init Auth")

            if progress is not None:
                progress.phase_start("Init Repo")
            repo_resp = client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=_github_headers(token))
            if repo_resp.status_code != 200:
                repo_error = AuthenticationError(
                    f"Cannot access target repository '{target}'; verify repo scope/permissions and repo visibility"
                )
                if progress is not None:
                    progress.phase_error("Init Repo", repo_error)
                raise repo_error
            if progress is not None:
                progress.phase_done("Init Repo")

            if progress is not None:
                progress.phase_start("Init Projects")
            viewer_projects_query = {"query": "query { viewer { projectsV2(first: 1) { nodes { id } } } }"}
            projects_resp = client.post(
                "https://api.github.com/graphql",
                headers=_github_headers(token),
                json=viewer_projects_query,
            )
            payload = (
                projects_resp.json()
                if projects_resp.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            if projects_resp.status_code != 200 or payload.get("errors"):
                projects_error = AuthenticationError(
                    "Token does not have sufficient project permissions; ensure project access is granted"
                )
                if progress is not None:
                    progress.phase_error("Init Projects", projects_error)
                raise projects_error
            if progress is not None:
                progress.phase_done("Init Projects")

            if progress is not None:
                progress.phase_start("Init Owner")
            owner_resp = client.get(f"https://api.github.com/users/{owner}", headers=_github_headers(token))
            if owner_resp.status_code != 200:
                if progress is not None:
                    progress.phase_done("Init Owner")
                return None
            owner_payload = owner_resp.json()
            owner_type = owner_payload.get("type")
            if owner_type == "Organization":
                if progress is not None:
                    progress.phase_done("Init Owner")
                return "org"
            if owner_type == "User":
                if progress is not None:
                    progress.phase_done("Init Owner")
                return "user"
            if progress is not None:
                progress.phase_done("Init Owner")
            return None


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "planpilot-init",
    }


def _check_classic_scopes(*, scopes_header: str | None) -> None:
    if scopes_header is None:
        return
    scopes = {scope.strip() for scope in scopes_header.split(",") if scope.strip()}
    missing = _REQUIRED_CLASSIC_SCOPES - scopes
    if missing:
        needed = ", ".join(sorted(missing))
        raise AuthenticationError(f"Token is missing required GitHub scopes: {needed}")


_service = InitAuthService()


def create_init_token_resolver(*, auth: str, static_token: str | None) -> TokenResolver:
    return InitTokenResolverFactory.create(auth=auth, static_token=static_token)


def resolve_init_token(
    *,
    auth: str,
    static_token: str | None,
    run_async: Callable[[Coroutine[object, object, str]], str] | None = None,
) -> str:
    return _service.resolve_token(auth=auth, static_token=static_token, run_async=run_async)


def validate_github_auth_for_init(*, token: str, target: str, progress: InitProgress | None = None) -> str | None:
    return _service.validate_github_auth_for_init(token=token, target=target, progress=progress)
