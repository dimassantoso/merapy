from __future__ import annotations

from typing import AsyncContextManager, Protocol, runtime_checkable


@runtime_checkable
class Locker(Protocol):
    """Distributed lock (Redis-backed by default).

    Returns a context manager so ``async with locker.acquire("key"):``
    is the natural usage.
    """

    def acquire(self, key: str, ttl: float = 30.0) -> AsyncContextManager[bool]: ...
    async def reset(self, key: str) -> None: ...
