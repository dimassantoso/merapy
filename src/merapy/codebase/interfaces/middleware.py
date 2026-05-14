from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol, runtime_checkable

from merapy.shared.token_claim import TokenClaim


@runtime_checkable
class TokenValidator(Protocol):
    """Validates a bearer token. Custom impls live in the generated service."""

    async def validate_token(self, token: str) -> TokenClaim: ...


@runtime_checkable
class BasicAuthValidator(Protocol):
    async def validate_basic(self, username: str, password: str) -> None: ...


@runtime_checkable
class ACLPermissionChecker(Protocol):
    """Checks whether a user holds a permission code. Returns the role on success."""

    async def check_permission(self, user_id: str, permission_code: str) -> str: ...


HTTPGuard = Callable[..., Awaitable[Any]]
"""A pre-built FastAPI dependency / Litestar guard that the module attaches
to a route or group."""


@runtime_checkable
class Middleware(Protocol):
    """Composite middleware bundle.

    Mirrors candi's ``interfaces.Middleware`` (HTTP + gRPC + GraphQL). The
    HTTP side returns adapter-friendly guards; the broker / worker side
    returns plain callables that decorate a ``WorkerHandlerFunc``.
    """

    async def basic(self, auth_key: str) -> None: ...
    async def bearer(self, token: str) -> TokenClaim: ...

    # HTTP — adapter-specific guards (FastAPI Depends or Litestar guard).
    def http_basic_auth(self) -> HTTPGuard: ...
    def http_bearer_auth(self) -> HTTPGuard: ...
    def http_multiple_auth(self) -> HTTPGuard: ...
    def http_permission_acl(self, permission_code: str) -> HTTPGuard: ...
    def http_cache(self) -> HTTPGuard: ...
