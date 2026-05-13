"""RabbitMQ broker (aio-pika)."""

from __future__ import annotations

import asyncio
from typing import Any

import aio_pika

from kapynis.shared.publisher_argument import PublisherArgument
from kapynis.codebase.interfaces.broker import Publisher  # noqa: F401  (type ref only)
from kapynis.codebase.types import Worker
from kapynis.config.env import Env
from kapynis.logger import get_logger

logger = get_logger(__name__)


class _RabbitMQPublisher:
    """Implements `Publisher` structurally."""

    __slots__ = ("_channel", "_exchange_name")

    def __init__(self, channel: aio_pika.abc.AbstractChannel, exchange_name: str) -> None:
        self._channel = channel
        self._exchange_name = exchange_name

    async def publish_message(self, args: PublisherArgument) -> None:
        exchange = (
            await self._channel.get_exchange(self._exchange_name)
            if self._exchange_name
            else self._channel.default_exchange
        )
        await exchange.publish(
            aio_pika.Message(
                body=args.message,
                headers=dict(args.headers),
                content_type="application/octet-stream",
                message_id=args.key or None,
            ),
            routing_key=args.topic,
        )


class RabbitMQBroker:
    __slots__ = ("_url", "_exchange_name", "_connection", "_channel")

    def __init__(self, url: str, exchange_name: str) -> None:
        self._url = url
        self._exchange_name = exchange_name
        self._connection: aio_pika.abc.AbstractConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None

    def name(self) -> Worker:
        return Worker.RABBITMQ

    def configuration(self) -> Any:
        return {"url": self._url, "exchange": self._exchange_name}

    def publisher(self) -> Publisher:
        if self._channel is None:
            raise RuntimeError("RabbitMQ broker not started — call start() first")
        return _RabbitMQPublisher(self._channel, self._exchange_name)

    async def start(self) -> None:
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()

    async def health(self) -> dict[str, str | None]:
        if self._connection is None or self._connection.is_closed:
            return {"rabbitmq": "disconnected"}
        return {"rabbitmq": None}

    async def close(self) -> None:
        if self._channel is not None:
            await self._channel.close()
        if self._connection is not None:
            await self._connection.close()


async def init_rabbitmq_broker(env: Env) -> RabbitMQBroker | None:
    if not env.rabbitmq.broker:
        return None
    broker = RabbitMQBroker(env.rabbitmq.broker, env.rabbitmq.exchange_name)
    try:
        await asyncio.wait_for(broker.start(), timeout=10.0)
    except (asyncio.TimeoutError, Exception) as exc:
        logger.error("rabbitmq.connect_failed", error=str(exc), url=env.rabbitmq.broker)
        return None
    logger.info("rabbitmq.connected", url=env.rabbitmq.broker)
    return broker
