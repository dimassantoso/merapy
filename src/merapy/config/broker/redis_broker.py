"""Redis pub/sub broker. Uses an existing ``RedisPool`` write client."""

from __future__ import annotations

from typing import Any

from redis.asyncio import Redis

from merapy.shared.publisher_argument import PublisherArgument
from merapy.codebase.interfaces.broker import Publisher  # noqa: F401  (type ref only)
from merapy.codebase.interfaces.database import RedisPool
from merapy.codebase.types import Worker
from merapy.logger import get_logger

logger = get_logger(__name__)


class _RedisPublisher:
    """Implements `Publisher` structurally."""

    __slots__ = ("_client",)

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def publish_message(self, args: PublisherArgument) -> None:
        await self._client.publish(args.topic, args.message)


class RedisBroker:
    __slots__ = ("_pool",)

    def __init__(self, pool: RedisPool) -> None:
        self._pool = pool

    def name(self) -> Worker:
        return Worker.REDIS_SUBSCRIBER

    def configuration(self) -> Any:
        return {"backend": "redis-pubsub"}

    def publisher(self) -> Publisher:
        return _RedisPublisher(self._pool.write())

    async def health(self) -> dict[str, str | None]:
        return await self._pool.health()

    async def close(self) -> None:
        # The pool is owned by RedisPoolImpl, not by us.
        return None


def init_redis_broker(pool: RedisPool | None) -> RedisBroker | None:
    if pool is None:
        return None
    logger.info("redis_broker.ready")
    return RedisBroker(pool)
