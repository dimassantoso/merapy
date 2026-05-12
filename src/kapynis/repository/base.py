"""Base classes for module repositories.

Generated module repositories subclass these; the framework provides the
session-acquisition pattern so all repositories behave consistently with
``with_transaction``.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncIterator

from kapynis.repository.transaction import current_session

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class BaseSQLRepository:
    """SQL repository base. Provides ``async with self._session() as s:`` access
    that participates in the ambient transaction when present.
    """

    __slots__ = ("_session_factory",)

    def __init__(self, session_factory: "async_sessionmaker[AsyncSession]") -> None:
        self._session_factory = session_factory

    @asynccontextmanager
    async def _session(self) -> AsyncIterator["AsyncSession"]:
        async with current_session(self._session_factory) as session:
            yield session


class BaseMongoRepository:
    """Mongo repository base. Holds read/write DB handles."""

    __slots__ = ("_read_db", "_write_db", "_collection")

    def __init__(
        self,
        read_db: "AsyncIOMotorDatabase",
        write_db: "AsyncIOMotorDatabase",
        collection: str,
    ) -> None:
        self._read_db = read_db
        self._write_db = write_db
        self._collection = collection

    @property
    def read_col(self) -> object:
        return self._read_db[self._collection]

    @property
    def write_col(self) -> object:
        return self._write_db[self._collection]
