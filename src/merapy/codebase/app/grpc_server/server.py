"""Async gRPC server (``grpc.aio``).

Each module's :class:`GRPCHandler` registers servicers via ``register(server)``.
Bearer auth / ACL are implemented as interceptors — modules can attach
their own per-method interceptors via the standard gRPC interceptor API.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import grpc
from grpc.aio import Server

from merapy.logger import get_logger

if TYPE_CHECKING:
    from merapy.codebase.factory.service_factory import ServiceFactory

logger = get_logger(__name__)


_MAX_MESSAGE_SIZE = 200 * 1024 * 1024  # 200 MiB — matches candi default


class GRPCServer:
    name = "grpc"

    __slots__ = ("_service", "_server", "_serve_event")

    def __init__(self, service: "ServiceFactory") -> None:
        self._service = service
        self._server: Server | None = None
        self._serve_event = asyncio.Event()

    def _build(self) -> Server:
        server = grpc.aio.server(
            options=[
                ("grpc.max_send_message_length", _MAX_MESSAGE_SIZE),
                ("grpc.max_receive_message_length", _MAX_MESSAGE_SIZE),
            ]
        )
        mounted: list[str] = []
        for module in self._service.modules():
            handler = module.grpc_handler()
            if handler is None:
                continue
            handler.register(server)
            mounted.append(module.name)
        logger.info("grpc.mounted", modules=mounted)
        return server

    async def serve(self) -> None:
        env = self._service.config().env
        self._server = self._build()
        address = f"[::]:{env.grpc_port}"
        self._server.add_insecure_port(address)
        await self._server.start()
        logger.info("grpc.serving", port=env.grpc_port)
        await self._server.wait_for_termination()

    async def shutdown(self) -> None:
        if self._server is not None:
            await self._server.stop(grace=10.0)
            self._server = None
