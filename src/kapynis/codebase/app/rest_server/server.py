"""FastAPI-based REST :class:`AppServerFactory`.

Mirrors candi's ``codebase/app/rest_server/rest_server.go``. Iterates
``service.modules()``, calls ``module.rest_handler().mount(router)`` on each,
attaches built-in middleware (CORS / tracer), and runs uvicorn.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI

from kapynis.codebase.app.rest_server.route_wrapper import FastAPIRouteWrapper
from kapynis.logger import get_logger
from kapynis.wrapper.http_handler import _install_middlewares, health_response

if TYPE_CHECKING:
    from kapynis.codebase.factory.service_factory import ServiceFactory

logger = get_logger(__name__)


class RESTServer:
    """Concrete :class:`AppServerFactory` running FastAPI under uvicorn."""

    name = "rest"

    __slots__ = ("_service", "_app", "_server", "_serve_task")

    def __init__(self, service: "ServiceFactory") -> None:
        self._service = service
        self._app = self._build_app()
        self._server: uvicorn.Server | None = None
        self._serve_task: asyncio.Task[None] | None = None

    def _build_app(self) -> FastAPI:
        env = self._service.config().env
        app = FastAPI(
            title=env.service_name,
            debug=env.debug_mode,
            openapi_url=f"{env.http_root_path.rstrip('/')}/openapi.json",
            docs_url=f"{env.http_root_path.rstrip('/')}/docs",
        )
        _install_middlewares(app, env)

        # Root health endpoint.
        @app.get(env.http_root_path or "/", include_in_schema=False)
        async def _root() -> object:
            return health_response(env.service_name, env.environment).to_response()

        # Module routes — single root wrapper, all modules mount into it.
        root = FastAPIRouteWrapper(prefix=env.http_root_path.rstrip("/"))
        mounted: list[str] = []
        for module in self._service.modules():
            handler = module.rest_handler()
            if handler is None:
                continue
            handler.mount(root)
            mounted.append(module.name)
        root.finalize(app)
        logger.info("rest.mounted", modules=mounted)
        return app

    async def serve(self) -> None:
        env = self._service.config().env
        config = uvicorn.Config(
            self._app,
            host="0.0.0.0",
            port=env.http_port,
            log_config=None,
            access_log=False,
            lifespan="off",
        )
        self._server = uvicorn.Server(config)
        logger.info("rest.serving", port=env.http_port)
        await self._server.serve()

    async def shutdown(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
            self._server.force_exit = False
            # Give uvicorn a moment to drain in-flight requests.
            await asyncio.sleep(0)
