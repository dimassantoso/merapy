"""Litestar :class:`AppServerFactory`."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import uvicorn
from litestar import Litestar
from litestar.config.cors import CORSConfig

from kapynis.codebase.app.litestar_rest_server.route_wrapper import LitestarRouteWrapper
from kapynis.logger import get_logger
from kapynis.wrapper.http_handler import health_response

if TYPE_CHECKING:
    from kapynis.codebase.factory.service_factory import ServiceFactory

logger = get_logger(__name__)


class LitestarRESTServer:
    name = "rest-litestar"

    __slots__ = ("_service", "_app", "_server")

    def __init__(self, service: "ServiceFactory") -> None:
        self._service = service
        self._app = self._build()
        self._server: uvicorn.Server | None = None

    def _build(self) -> Litestar:
        env = self._service.config().env
        cors = CORSConfig(
            allow_origins=env.cors_allow_origins,
            allow_methods=env.cors_allow_methods,
            allow_headers=env.cors_allow_headers,
            allow_credentials=env.cors_allow_credentials,
        )
        root = LitestarRouteWrapper(prefix=env.http_root_path.rstrip("/") or "/")
        mounted: list[str] = []
        for module in self._service.modules():
            handler = module.rest_handler()
            if handler is None:
                continue
            handler.mount(root)
            mounted.append(module.name)

        from litestar import get as get_route

        @get_route("/")
        async def _root() -> dict[str, object]:
            return health_response(env.service_name, env.environment).model_dump(exclude_none=True)

        app = Litestar(
            route_handlers=[_root, root.build_router()],
            cors_config=cors,
            debug=env.debug_mode,
        )
        logger.info("litestar.mounted", modules=mounted)
        return app

    async def serve(self) -> None:
        env = self._service.config().env
        config = uvicorn.Config(
            self._app, host="0.0.0.0", port=env.http_port, log_config=None, access_log=False
        )
        self._server = uvicorn.Server(config)
        logger.info("litestar.serving", port=env.http_port)
        await self._server.serve()

    async def shutdown(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
            await asyncio.sleep(0)
