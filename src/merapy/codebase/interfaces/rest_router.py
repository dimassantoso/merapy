from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol, runtime_checkable

RouteHandler = Callable[..., Awaitable[Any]]
"""Async callable that handles an HTTP request.

Signature is intentionally loose so adapters (FastAPI / Litestar) can pass
their own request / response types. Module handlers should be plain async
functions returning a Starlette ``Response`` (FastAPI) or Litestar response.
"""

HTTPMiddleware = Callable[..., Any]
"""Adapter-specific middleware. FastAPI uses ``Depends``-style callables,
Litestar uses guards or middleware; module code passes pre-wrapped values
obtained from ``Dependency.middleware``."""


@runtime_checkable
class RESTRouter(Protocol):
    """Framework-agnostic router contract.

    Modules call this interface only; the concrete adapter (FastAPI APIRouter
    or Litestar Router) is selected at boot. Mirrors candi's
    ``interfaces.RESTRouter`` which wraps chi / echo / fiber.
    """

    def use(self, *middlewares: HTTPMiddleware) -> None: ...

    def group(self, pattern: str, *middlewares: HTTPMiddleware) -> "RESTRouter": ...

    def handle(
        self,
        method: str,
        pattern: str,
        handler: RouteHandler,
        *middlewares: HTTPMiddleware,
    ) -> None: ...

    def get(
        self, pattern: str, handler: RouteHandler, *middlewares: HTTPMiddleware
    ) -> None: ...
    def post(
        self, pattern: str, handler: RouteHandler, *middlewares: HTTPMiddleware
    ) -> None: ...
    def put(
        self, pattern: str, handler: RouteHandler, *middlewares: HTTPMiddleware
    ) -> None: ...
    def patch(
        self, pattern: str, handler: RouteHandler, *middlewares: HTTPMiddleware
    ) -> None: ...
    def delete(
        self, pattern: str, handler: RouteHandler, *middlewares: HTTPMiddleware
    ) -> None: ...
    def head(
        self, pattern: str, handler: RouteHandler, *middlewares: HTTPMiddleware
    ) -> None: ...
    def options(
        self, pattern: str, handler: RouteHandler, *middlewares: HTTPMiddleware
    ) -> None: ...
