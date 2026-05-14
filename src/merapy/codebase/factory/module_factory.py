from __future__ import annotations

from typing import Protocol, runtime_checkable

from merapy.codebase.interfaces.handlers import (
    GraphQLHandler,
    GRPCHandler,
    RESTHandler,
    ServerHandler,
    WorkerHandler,
)
from merapy.codebase.types import Server, Worker


@runtime_checkable
class ModuleFactory(Protocol):
    """A bundle of delivery handlers for one bounded context.

    Mirrors candi's ``factory.ModuleFactory``. Any accessor may return ``None``
    when the module doesn't expose that delivery surface.
    """

    @property
    def name(self) -> str: ...

    def rest_handler(self) -> RESTHandler | None: ...
    def grpc_handler(self) -> GRPCHandler | None: ...
    def graphql_handler(self) -> GraphQLHandler | None: ...
    def worker_handler(self, worker_type: Worker) -> WorkerHandler | None: ...
    def server_handler(self, server_type: Server | str) -> ServerHandler | None: ...
