"""Enums and lightweight value types shared across the framework.

Mirrors candi's ``codebase/factory/types/const.go`` (Server/Worker/Module/Service)
and ``codebase/factory/types/worker_type.go`` (WorkerHandler / WorkerHandlerGroup).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Awaitable, Callable, Mapping


class Server(StrEnum):
    REST = "rest"
    GRPC = "grpc"
    GRAPHQL = "graphql"


class Worker(StrEnum):
    KAFKA = "kafka"
    REDIS_SUBSCRIBER = "redis_subscriber"
    RABBITMQ = "rabbit_mq"
    SCHEDULER = "scheduler"
    TASK_QUEUE = "task_queue"
    POSTGRES_LISTENER = "postgres_listener"


class Module(str):
    """Module name newtype (kept as plain str for ergonomics)."""


class Service(str):
    """Service name newtype."""


@dataclass(slots=True)
class EventContext:
    """Per-event execution context handed to worker handlers.

    Mirrors candi's ``candishared.EventContext``. The body is materialized as
    ``bytes`` to keep the type async-friendly across all worker transports.
    """

    worker_type: str
    handler_route: str
    key: str = ""
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)


WorkerHandlerFunc = Callable[[EventContext], Awaitable[None]]


@dataclass(slots=True)
class WorkerHandlerEntry:
    """A single registered worker handler."""

    pattern: str
    handler: WorkerHandlerFunc
    auto_ack: bool = True
    disable_trace: bool = False
    configs: Mapping[str, Any] = field(default_factory=dict)


class WorkerHandlerGroup:
    """Collects worker handlers from a module's worker handler.

    Each ``AppServerFactory`` worker (Kafka, Cron, ...) iterates modules,
    builds a group per module, then registers all handlers with the underlying
    transport.
    """

    __slots__ = ("handlers",)

    def __init__(self) -> None:
        self.handlers: list[WorkerHandlerEntry] = []

    def add(
        self,
        pattern: str,
        handler: WorkerHandlerFunc,
        *,
        auto_ack: bool = True,
        disable_trace: bool = False,
        **configs: Any,
    ) -> None:
        self.handlers.append(
            WorkerHandlerEntry(
                pattern=pattern,
                handler=handler,
                auto_ack=auto_ack,
                disable_trace=disable_trace,
                configs=configs,
            )
        )


@dataclass(slots=True)
class PublisherArgument:
    """Arguments passed to a broker's ``Publisher.publish_message``.

    Mirrors candi's ``candishared.PublisherArgument``.
    """

    topic: str
    key: str = ""
    message: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)
    delay: float = 0.0
    extras: dict[str, Any] = field(default_factory=dict)
