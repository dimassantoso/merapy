from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from merapy.codebase.interfaces.cache import Cache
from merapy.codebase.interfaces.closer import Closer

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker


@runtime_checkable
class SQLDatabase(Closer, Protocol):
    """Read/write SQLAlchemy AsyncEngine pair.

    ``read_engine`` may equal ``write_engine`` when no replica is configured.
    """

    def read_engine(self) -> "AsyncEngine": ...
    def write_engine(self) -> "AsyncEngine": ...
    def session_factory(self) -> "async_sessionmaker": ...
    async def health(self) -> dict[str, str | None]: ...


@runtime_checkable
class MongoDatabase(Closer, Protocol):
    def read_db(self) -> "AsyncIOMotorDatabase": ...
    def write_db(self) -> "AsyncIOMotorDatabase": ...
    async def health(self) -> dict[str, str | None]: ...


@runtime_checkable
class RedisPool(Closer, Protocol):
    def read(self) -> "Redis": ...
    def write(self) -> "Redis": ...
    def cache(self) -> Cache: ...
    async def health(self) -> dict[str, str | None]: ...
