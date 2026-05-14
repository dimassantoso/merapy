from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from merapy.codebase.interfaces.rest_router import RESTRouter
from merapy.codebase.types import Server, WorkerHandlerGroup


@runtime_checkable
class RESTHandler(Protocol):
    """A module's REST delivery. Implements ``mount(router)``."""

    def mount(self, router: RESTRouter) -> None: ...


@runtime_checkable
class GRPCHandler(Protocol):
    """A module's gRPC delivery."""

    def register(self, server: Any) -> None: ...


@runtime_checkable
class GraphQLHandler(Protocol):
    """A module's GraphQL delivery — exposes query / mutation / subscription roots."""

    def query(self) -> Any: ...
    def mutation(self) -> Any: ...
    def subscription(self) -> Any: ...


@runtime_checkable
class WorkerHandler(Protocol):
    """A module's worker delivery. Mounts handlers into the supplied group."""

    def mount_handlers(self, group: WorkerHandlerGroup) -> None: ...


@runtime_checkable
class ServerHandler(Protocol):
    """Generic extension point for custom server types (e.g. Telegram bot).

    Mirrors candi's ``interfaces.ServerHandler``. The ``server_type`` keyspace
    is open — modules may register handlers for arbitrary custom servers.
    """

    def server_type(self) -> Server | str: ...
    def mount_handlers(self, group: Any) -> None: ...
