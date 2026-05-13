"""GraphQL server using ``strawberry-graphql`` over FastAPI.

Each module's :class:`GraphQLHandler` returns ``query()`` / ``mutation()`` /
``subscription()`` types (strawberry classes annotated with ``@strawberry.type``).
The server merges them into a single Schema and mounts ``/graphql``.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import strawberry
import uvicorn
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

from kapynis.logger import get_logger

if TYPE_CHECKING:
    from kapynis.codebase.factory.service_factory import ServiceFactory

logger = get_logger(__name__)


def _merge(roots: list[type], default_name: str) -> type | None:
    """Merge multiple strawberry root types into one via multiple inheritance."""
    roots = [r for r in roots if r is not None]
    if not roots:
        return None
    if len(roots) == 1:
        return roots[0]
    merged = type(default_name, tuple(roots), {})
    return strawberry.type(merged)


class GraphQLServer:
    name = "graphql"

    __slots__ = ("_service", "_app", "_server")

    def __init__(self, service: "ServiceFactory") -> None:
        self._service = service
        self._app = self._build()
        self._server: uvicorn.Server | None = None

    def _build(self) -> FastAPI:
        env = self._service.config().env
        queries: list[type] = []
        mutations: list[type] = []
        subscriptions: list[type] = []
        for module in self._service.modules():
            h = module.graphql_handler()
            if h is None:
                continue
            q, m, s = h.query(), h.mutation(), h.subscription()
            if q is not None:
                queries.append(q)
            if m is not None:
                mutations.append(m)
            if s is not None:
                subscriptions.append(s)

        if not queries:
            logger.warning("graphql.no_query_root")
            queries.append(_default_empty_query())

        schema = strawberry.Schema(
            query=_merge(queries, "Query") or _default_empty_query(),
            mutation=_merge(mutations, "Mutation"),
            subscription=_merge(subscriptions, "Subscription"),
        )
        app = FastAPI(title=f"{env.service_name} (graphql)", debug=env.debug_mode)
        graphql_router: GraphQLRouter[Any, Any] = GraphQLRouter(schema)
        app.include_router(graphql_router, prefix="/graphql")
        return app

    async def serve(self) -> None:
        env = self._service.config().env
        # Use http_port + 100 to avoid clash with REST. Override via env if needed.
        port = env.http_port + 100
        config = uvicorn.Config(self._app, host="0.0.0.0", port=port, log_config=None, access_log=False, lifespan="off")
        self._server = uvicorn.Server(config)
        logger.info("graphql.serving", port=port)
        await self._server.serve()

    async def shutdown(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
            await asyncio.sleep(0)


def _default_empty_query() -> type:
    @strawberry.type
    class Query:
        @strawberry.field
        def health(self) -> str:
            return "ok"

    return Query
