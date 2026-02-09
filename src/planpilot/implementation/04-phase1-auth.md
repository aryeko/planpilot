# Phase 1: Auth Module

**Layer:** L2 (Core)
**Branch:** `v2/auth`
**Phase:** 1 (parallel with plan, renderers, engine)
**Dependencies:** Contracts only (`planpilot.contracts.config`, `planpilot.contracts.exceptions`)
**Design doc:** [`../docs/modules/auth.md`](../docs/modules/auth.md)

---

## Files to Create

| File | Contents |
|------|----------|
| `auth/__init__.py` | Exports `TokenResolver`, `create_token_resolver` |
| `auth/base.py` | `TokenResolver` ABC |
| `auth/factory.py` | `create_token_resolver()` factory |
| `auth/gh_cli.py` | `GhCliTokenResolver` |
| `auth/env.py` | `EnvTokenResolver` |
| `auth/static.py` | `StaticTokenResolver` |

---

## Signatures

```python
# base.py
class TokenResolver(ABC):
    @abstractmethod
    async def resolve(self) -> str:
        """Resolve and return an authentication token.
        Raises: AuthenticationError
        """

# gh_cli.py
class GhCliTokenResolver(TokenResolver):
    """Runs `gh auth token --hostname <host>` as subprocess."""
    def __init__(self, hostname: str = "github.com") -> None: ...
    async def resolve(self) -> str: ...

# env.py
class EnvTokenResolver(TokenResolver):
    """Reads GITHUB_TOKEN environment variable."""
    async def resolve(self) -> str: ...

# static.py
class StaticTokenResolver(TokenResolver):
    """Uses token string directly."""
    def __init__(self, token: str) -> None: ...
    async def resolve(self) -> str: ...

# factory.py
RESOLVERS: dict[str, type[TokenResolver]] = {
    "gh-cli": GhCliTokenResolver,
    "env": EnvTokenResolver,
    "token": StaticTokenResolver,
}

def create_token_resolver(config: PlanPilotConfig) -> TokenResolver:
    """Create resolver from config.auth.
    Raises: ConfigError if unknown auth method.
    """
```

---

## Test Strategy

| Test File | Key Cases |
|-----------|-----------|
| `test_gh_cli.py` | Mock `asyncio.create_subprocess_exec`, success returns token, subprocess failure -> AuthenticationError, empty output -> AuthenticationError |
| `test_env.py` | `monkeypatch.setenv("GITHUB_TOKEN", "tok")` success, unset -> AuthenticationError, empty -> AuthenticationError |
| `test_static.py` | Direct token success, empty string -> AuthenticationError |
| `test_factory.py` | Each auth value creates correct resolver type, unknown auth -> ConfigError, gh-cli hostname from config.target |
