"""Redis async pool + Cache implementation.

One ``Redis`` client per read / write DSN; a shared ``Cache`` view over
the write client.
"""

from __future__ import annotations

from redis.asyncio import Redis, from_url

from merapy.codebase.interfaces.cache import Cache
from merapy.config.env import Env
from merapy.logger import get_logger

logger = get_logger(__name__)


class RedisCache:
    """Concrete `Cache` impl backed by a redis.asyncio client.

    Does not inherit from `Cache` — `Cache` is a `Protocol`, and explicit
    subclassing would make `RedisCache` itself a Protocol per PEP 544.
    Structural typing handles the contract; runtime_checkable lets
    ``isinstance(x, Cache)`` still succeed.
    """

    __slots__ = ("_client",)

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def get(self, key: str) -> bytes | None:
        result = await self._client.get(key)
        return result if isinstance(result, bytes) else (result.encode() if result else None)

    async def set(self, key: str, value: bytes, ttl: float | None = None) -> None:
        if ttl is not None:
            await self._client.set(key, value, ex=int(ttl))
        else:
            await self._client.set(key, value)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self._client.exists(key))


class RedisPoolImpl:
    __slots__ = ("_read", "_write", "_cache")

    def __init__(self, read_dsn: str, write_dsn: str) -> None:
        self._read = from_url(read_dsn, decode_responses=False)
        self._write = self._read if read_dsn == write_dsn else from_url(write_dsn, decode_responses=False)
        self._cache = RedisCache(self._write)

    def read(self) -> Redis:
        return self._read

    def write(self) -> Redis:
        return self._write

    def cache(self) -> Cache:
        return self._cache

    async def health(self) -> dict[str, str | None]:
        result: dict[str, str | None] = {"read": None, "write": None}
        for label, client in (("read", self._read), ("write", self._write)):
            try:
                await client.ping()
            except Exception as e:
                result[label] = str(e)
        return result

    async def close(self) -> None:
        await self._write.aclose()
        if self._read is not self._write:
            await self._read.aclose()


def init_redis(env: Env) -> RedisPoolImpl | None:
    if not env.redis_dsn_write:
        return None
    pool = RedisPoolImpl(
        read_dsn=env.redis_dsn_read or env.redis_dsn_write,
        write_dsn=env.redis_dsn_write,
    )
    logger.info("redis.connected", write=True)
    return pool
