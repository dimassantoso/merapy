"""Enums and lightweight value types shared across the framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Awaitable, Callable, Mapping


class Server(StrEnum):
    REST = "rest"
    GRPC = "grpc"
    GRAPHQL = "graphql"
    # Plugin-defined server types (raw string values accepted via StrEnum subclassing)
    P2P_TCP = "p2p_tcp"
    P2P_UDP = "p2p_udp"


class Worker(StrEnum):
    KAFKA = "kafka"
    REDIS_SUBSCRIBER = "redis_subscriber"
    RABBITMQ = "rabbit_mq"
    SCHEDULER = "scheduler"
    TASK_QUEUE = "task_queue"
    POSTGRES_LISTENER = "postgres_listener"
    # Plugin-defined worker types
    AMAZONSQS = "amazonsqs_broker"
    GCP_PUBSUB = "gcp_pubsub"
    STOMP = "stomp_broker"


class Module(str):
    """Module name newtype (kept as plain str for ergonomics)."""


class Service(str):
    """Service name newtype."""


@dataclass(slots=True)
class EventContext:
    """Per-event execution context handed to worker handlers.

    The body is materialized as ``bytes`` to keep the type async-friendly
    across all worker transports.
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
    """Arguments passed to a broker's ``Publisher.publish_message``."""

    topic: str
    key: str = ""
    message: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)
    delay: float = 0.0
    extras: dict[str, Any] = field(default_factory=dict)
