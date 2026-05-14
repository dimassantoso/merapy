"""Redis-backed distributed lock.

Uses the standard ``SET key value NX PX`` pattern with a randomly generated
token to ensure only the lock owner can release it.
"""

from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from typing import AsyncIterator

from redis.asyncio import Redis

_RELEASE_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""


class RedisLocker:
    __slots__ = ("_client", "_prefix")

    def __init__(self, client: Redis, prefix: str = "lock:") -> None:
        self._client = client
        self._prefix = prefix

    @asynccontextmanager
    async def acquire(self, key: str, ttl: float = 30.0) -> AsyncIterator[bool]:
        """Try to acquire ``key`` for ``ttl`` seconds. Yields True on success.

        Non-blocking: if the lock is held, yields False immediately. Caller
        decides whether to retry.
        """
        token = secrets.token_hex(16)
        full_key = self._prefix + key
        ok = await self._client.set(full_key, token, nx=True, px=int(ttl * 1000))
        try:
            yield bool(ok)
        finally:
            if ok:
                await self._client.eval(_RELEASE_SCRIPT, 1, full_key, token)

    async def reset(self, key: str) -> None:
        await self._client.delete(self._prefix + key)
