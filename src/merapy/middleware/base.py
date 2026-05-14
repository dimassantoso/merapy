"""Composite Middleware impl + builder."""

from __future__ import annotations

import base64
from typing import Awaitable, Callable, Self

from fastapi import HTTPException, Request, status

from merapy.shared.token_claim import TokenClaim
from merapy.codebase.interfaces.cache import Cache
from merapy.codebase.interfaces.middleware import (
    ACLPermissionChecker,
    BasicAuthValidator,
    HTTPGuard,
    TokenValidator,
)

_TOKEN_CLAIM_KEY = "_merapy_token_claim"
_AUTHORIZATION_HEADER = "authorization"


class MiddlewareImpl:
    """Composite middleware implementation.

    Exposes ``http_*_auth`` guards as plain async callables that read the
    request, validate the credential, and stash the resulting
    :class:`TokenClaim` on ``request.state`` (FastAPI's per-request scope).
    """

    __slots__ = (
        "_token_validator",
        "_basic_auth_validator",
        "_acl_permission_checker",
        "_cache",
        "_user_id_extractor",
    )

    def __init__(
        self,
        token_validator: TokenValidator,
        basic_auth_validator: BasicAuthValidator,
        acl_permission_checker: ACLPermissionChecker,
        cache: Cache | None,
        user_id_extractor: Callable[[TokenClaim], str] | None = None,
    ) -> None:
        self._token_validator = token_validator
        self._basic_auth_validator = basic_auth_validator
        self._acl_permission_checker = acl_permission_checker
        self._cache = cache
        self._user_id_extractor = user_id_extractor or (lambda c: c.subject)

    # Direct validator calls — useful from worker handlers that aren't HTTP.
    async def basic(self, auth_key: str) -> None:
        await self._validate_basic(auth_key)

    async def bearer(self, token: str) -> TokenClaim:
        return await self._token_validator.validate_token(token)

    # HTTP guards (FastAPI dependencies).
    def http_basic_auth(self) -> HTTPGuard:
        async def guard(request: Request) -> None:
            auth = request.headers.get(_AUTHORIZATION_HEADER, "")
            if not auth.lower().startswith("basic "):
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing basic auth header")
            await self._validate_basic(auth[6:].strip())

        return guard

    def http_bearer_auth(self) -> HTTPGuard:
        async def guard(request: Request) -> TokenClaim:
            auth = request.headers.get(_AUTHORIZATION_HEADER, "")
            if not auth.lower().startswith("bearer "):
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
            token = auth[7:].strip()
            try:
                claim = await self._token_validator.validate_token(token)
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e
            setattr(request.state, _TOKEN_CLAIM_KEY, claim)
            return claim

        return guard

    def http_multiple_auth(self) -> HTTPGuard:
        """Bearer OR basic — try bearer first, fall back to basic."""

        async def guard(request: Request) -> None:
            auth = request.headers.get(_AUTHORIZATION_HEADER, "")
            lower = auth.lower()
            if lower.startswith("bearer "):
                token = auth[7:].strip()
                try:
                    claim = await self._token_validator.validate_token(token)
                except Exception as e:
                    raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e
                setattr(request.state, _TOKEN_CLAIM_KEY, claim)
                return
            if lower.startswith("basic "):
                await self._validate_basic(auth[6:].strip())
                return
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing credentials")

        return guard

    def http_permission_acl(self, permission_code: str) -> HTTPGuard:
        async def guard(request: Request) -> None:
            claim: TokenClaim | None = getattr(request.state, _TOKEN_CLAIM_KEY, None)
            if claim is None:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN, "ACL requires authenticated bearer token"
                )
            user_id = self._user_id_extractor(claim)
            try:
                role = await self._acl_permission_checker.check_permission(
                    user_id, permission_code
                )
            except Exception as e:
                raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e
            claim.role = role or claim.role

        return guard

    def http_cache(self) -> HTTPGuard:
        """No-op guard placeholder. Implement via dedicated ASGI middleware
        if response caching is needed.
        """

        async def guard(request: Request) -> None:  # noqa: ARG001
            return None

        return guard

    async def _validate_basic(self, encoded: str) -> None:
        try:
            decoded = base64.b64decode(encoded).decode()
            username, _, password = decoded.partition(":")
        except Exception as e:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "malformed basic auth") from e
        try:
            await self._basic_auth_validator.validate_basic(username, password)
        except Exception as e:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e


class MiddlewareBuilder:
    """Fluent builder for :class:`MiddlewareImpl`."""

    def __init__(self) -> None:
        self._token: TokenValidator | None = None
        self._basic: BasicAuthValidator | None = None
        self._acl: ACLPermissionChecker | None = None
        self._cache: Cache | None = None
        self._extractor: Callable[[TokenClaim], str] | None = None

    def with_token_validator(self, v: TokenValidator) -> Self:
        self._token = v
        return self

    def with_basic_auth_validator(self, v: BasicAuthValidator) -> Self:
        self._basic = v
        return self

    def with_acl_permission_checker(self, v: ACLPermissionChecker) -> Self:
        self._acl = v
        return self

    def with_cache(self, c: Cache | None) -> Self:
        self._cache = c
        return self

    def with_user_id_extractor(self, fn: Callable[[TokenClaim], str]) -> Self:
        self._extractor = fn
        return self

    def build(self) -> MiddlewareImpl:
        if self._token is None or self._basic is None or self._acl is None:
            raise RuntimeError(
                "MiddlewareBuilder requires token, basic auth, and ACL validators"
            )
        return MiddlewareImpl(
            token_validator=self._token,
            basic_auth_validator=self._basic,
            acl_permission_checker=self._acl,
            cache=self._cache,
            user_id_extractor=self._extractor,
        )


# Convenience: retrieve the currently-authenticated TokenClaim from a Request.
def get_token_claim(request: Request) -> TokenClaim | None:
    return getattr(request.state, _TOKEN_CLAIM_KEY, None)
