from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from merapy.shared.publisher_argument import PublisherArgument
from merapy.codebase.interfaces.closer import Closer
from merapy.codebase.types import Worker


@runtime_checkable
class Publisher(Protocol):
    async def publish_message(self, args: PublisherArgument) -> None: ...


@runtime_checkable
class Broker(Closer, Protocol):
    """Broker (Kafka / RabbitMQ / Redis) wrapper.

    Mirrors candi's ``interfaces.Broker``.
    """

    def name(self) -> Worker: ...
    def configuration(self) -> Any: ...
    def publisher(self) -> Publisher: ...
    async def health(self) -> dict[str, str | None]: ...
