"""FastAPI adapter for :class:`RESTRouter`.

Modules call the ``RESTRouter`` interface only; the wrapper translates
``group`` / ``get`` / etc. into FastAPI ``APIRouter`` operations.

Child routers are wired into their parents at :meth:`finalize` time — this
defers the ``include_router`` call until all module ``mount()`` calls have
finished registering their routes, so the assembled tree is complete.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, FastAPI

from merapy.codebase.interfaces.rest_router import HTTPMiddleware, RouteHandler

if TYPE_CHECKING:
    pass


def _deps(middlewares: tuple[HTTPMiddleware, ...]) -> list[object]:
    return [Depends(mw) for mw in middlewares]


class FastAPIRouteWrapper:
    """Concrete ``RESTRouter`` impl over ``fastapi.APIRouter``."""

    __slots__ = ("_router", "_children", "_default_deps")

    def __init__(
        self,
        prefix: str = "",
        middlewares: tuple[HTTPMiddleware, ...] = (),
    ) -> None:
        self._router = APIRouter(prefix=prefix, dependencies=_deps(middlewares))
        self._children: list[FastAPIRouteWrapper] = []
        self._default_deps: list[object] = []

    def use(self, *middlewares: HTTPMiddleware) -> None:
        # FastAPI APIRouter doesn't support post-hoc dependency injection on
        # already-attached routes, so we accumulate and apply to subsequent adds.
        self._default_deps.extend(_deps(middlewares))

    def group(self, pattern: str, *middlewares: HTTPMiddleware) -> "FastAPIRouteWrapper":
        child = FastAPIRouteWrapper(prefix=pattern, middlewares=middlewares)
        # Carry parent's accumulated deps into the child.
        child._default_deps.extend(self._default_deps)
        self._children.append(child)
        return child

    def handle(
        self,
        method: str,
        pattern: str,
        handler: RouteHandler,
        *middlewares: HTTPMiddleware,
    ) -> None:
        deps = self._default_deps + _deps(middlewares)
        self._router.add_api_route(
            pattern,
            handler,
            methods=[method.upper()],
            dependencies=deps,
        )

    def get(self, pattern: str, handler: RouteHandler, *middlewares: HTTPMiddleware) -> None:
        self.handle("GET", pattern, handler, *middlewares)

    def post(self, pattern: str, handler: RouteHandler, *middlewares: HTTPMiddleware) -> None:
        self.handle("POST", pattern, handler, *middlewares)

    def put(self, pattern: str, handler: RouteHandler, *middlewares: HTTPMiddleware) -> None:
        self.handle("PUT", pattern, handler, *middlewares)

    def patch(self, pattern: str, handler: RouteHandler, *middlewares: HTTPMiddleware) -> None:
        self.handle("PATCH", pattern, handler, *middlewares)

    def delete(self, pattern: str, handler: RouteHandler, *middlewares: HTTPMiddleware) -> None:
        self.handle("DELETE", pattern, handler, *middlewares)

    def head(self, pattern: str, handler: RouteHandler, *middlewares: HTTPMiddleware) -> None:
        self.handle("HEAD", pattern, handler, *middlewares)

    def options(self, pattern: str, handler: RouteHandler, *middlewares: HTTPMiddleware) -> None:
        self.handle("OPTIONS", pattern, handler, *middlewares)

    def finalize(self, app: FastAPI) -> None:
        """Recursively include all children, then mount ``self._router`` on the FastAPI app."""
        # Children include themselves into self before self is included into app.
        for child in self._children:
            child._mount_on_parent(self._router)
        app.include_router(self._router)

    def _mount_on_parent(self, parent: APIRouter) -> None:
        for child in self._children:
            child._mount_on_parent(self._router)
        parent.include_router(self._router)
