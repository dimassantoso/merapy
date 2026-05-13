"""Kafka broker (aiokafka). Provides a Publisher; consumer lives in the worker."""

from __future__ import annotations

import asyncio
from typing import Any

from aiokafka import AIOKafkaProducer

from kapynis.shared.publisher_argument import PublisherArgument
from kapynis.codebase.interfaces.broker import Publisher  # noqa: F401  (type ref only)
from kapynis.codebase.types import Worker
from kapynis.config.env import Env
from kapynis.logger import get_logger

logger = get_logger(__name__)


class _KafkaPublisher:
    """Implements `Publisher` structurally — see RedisCache note."""

    __slots__ = ("_producer",)

    def __init__(self, producer: AIOKafkaProducer) -> None:
        self._producer = producer

    async def publish_message(self, args: PublisherArgument) -> None:
        headers = [(k, v.encode()) for k, v in args.headers.items()]
        await self._producer.send_and_wait(
            args.topic,
            value=args.message,
            key=args.key.encode() if args.key else None,
            headers=headers,
        )


class KafkaBroker:
    __slots__ = ("_producer", "_brokers", "_client_id")

    def __init__(self, brokers: list[str], client_id: str) -> None:
        self._brokers = brokers
        self._client_id = client_id
        self._producer = AIOKafkaProducer(
            bootstrap_servers=brokers,
            client_id=client_id or None,
        )

    def name(self) -> Worker:
        return Worker.KAFKA

    def configuration(self) -> Any:
        return {"brokers": self._brokers, "client_id": self._client_id}

    def publisher(self) -> Publisher:
        return _KafkaPublisher(self._producer)

    async def start(self) -> None:
        await self._producer.start()

    async def health(self) -> dict[str, str | None]:
        try:
            md = await self._producer.client.fetch_all_metadata()
            return {"kafka": None if md.brokers() else "no brokers"}
        except Exception as e:
            return {"kafka": str(e)}

    async def close(self) -> None:
        await self._producer.stop()


async def init_kafka_broker(env: Env) -> KafkaBroker | None:
    if not env.kafka.brokers:
        return None
    broker = KafkaBroker(env.kafka.brokers, env.kafka.client_id)
    try:
        await asyncio.wait_for(broker.start(), timeout=10.0)
    except (asyncio.TimeoutError, Exception) as exc:
        logger.error("kafka.connect_failed", error=str(exc), brokers=env.kafka.brokers)
        return None
    logger.info("kafka.connected", brokers=env.kafka.brokers)
    return broker
