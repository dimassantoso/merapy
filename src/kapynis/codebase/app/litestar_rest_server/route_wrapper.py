"""Litestar adapter for :class:`RESTRouter`.

Litestar route handlers are decorated callables registered up-front, unlike
FastAPI's ``add_api_route``. The wrapper accumulates ``(method, path,
handler, guards)`` tuples and assembles a ``litestar.Router`` (or nested
routers) at :meth:`finalize`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from litestar import Router, delete, get, head, options, patch, post, put
from litestar.handlers.http_handlers import HTTPRouteHandler

from kapynis.codebase.interfaces.rest_router import HTTPMiddleware, RouteHandler

if TYPE_CHECKING:
    from litestar import Litestar

_METHOD_DECORATORS = {
    "GET": get,
    "POST": post,
    "PUT": put,
    "PATCH": patch,
    "DELETE": delete,
    "HEAD": head,
    "OPTIONS": options,
}


@dataclass
class _RouteSpec:
    method: str
    pattern: str
    handler: RouteHandler
    guards: tuple[HTTPMiddleware, ...]


@dataclass
class _GroupSpec:
    prefix: str
    guards: tuple[HTTPMiddleware, ...]
    routes: list[_RouteSpec] = field(default_factory=list)
    children: list["LitestarRouteWrapper"] = field(default_factory=list)


class LitestarRouteWrapper:
    """Concrete ``RESTRouter`` impl that builds a ``litestar.Router`` lazily."""

    __slots__ = ("_spec", "_default_guards")

    def __init__(self, prefix: str = "", middlewares: tuple[HTTPMiddleware, ...] = ()) -> None:
        self._spec = _GroupSpec(prefix=prefix, guards=middlewares)
        self._default_guards: list[HTTPMiddleware] = []

    def use(self, *middlewares: HTTPMiddleware) -> None:
        self._default_guards.extend(middlewares)

    def group(self, pattern: str, *middlewares: HTTPMiddleware) -> "LitestarRouteWrapper":
        child = LitestarRouteWrapper(prefix=pattern, middlewares=middlewares)
        child._default_guards.extend(self._default_guards)
        self._spec.children.append(child)
        return child

    def handle(
        self,
        method: str,
        pattern: str,
        handler: RouteHandler,
        *middlewares: HTTPMiddleware,
    ) -> None:
        guards = tuple(self._default_guards) + middlewares
        self._spec.routes.append(_RouteSpec(method.upper(), pattern, handler, guards))

    def get(self, p: str, h: RouteHandler, *m: HTTPMiddleware) -> None:
        self.handle("GET", p, h, *m)

    def post(self, p: str, h: RouteHandler, *m: HTTPMiddleware) -> None:
        self.handle("POST", p, h, *m)

    def put(self, p: str, h: RouteHandler, *m: HTTPMiddleware) -> None:
        self.handle("PUT", p, h, *m)

    def patch(self, p: str, h: RouteHandler, *m: HTTPMiddleware) -> None:
        self.handle("PATCH", p, h, *m)

    def delete(self, p: str, h: RouteHandler, *m: HTTPMiddleware) -> None:
        self.handle("DELETE", p, h, *m)

    def head(self, p: str, h: RouteHandler, *m: HTTPMiddleware) -> None:
        self.handle("HEAD", p, h, *m)

    def options(self, p: str, h: RouteHandler, *m: HTTPMiddleware) -> None:
        self.handle("OPTIONS", p, h, *m)

    def build_router(self) -> Router:
        route_handlers: list[HTTPRouteHandler | Router] = []
        for spec in self._spec.routes:
            decorator = _METHOD_DECORATORS[spec.method]
            route_handlers.append(decorator(spec.pattern, guards=list(spec.guards))(spec.handler))
        for child in self._spec.children:
            route_handlers.append(child.build_router())
        return Router(path=self._spec.prefix or "/", route_handlers=route_handlers, guards=list(self._spec.guards))

    def finalize(self, app: "Litestar") -> None:
        app.register(self.build_router())
