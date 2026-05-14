"""SQLAlchemy 2.x async engine pair.

Returns a single object that implements :class:`SQLDatabase` and is also
a :class:`Closer`.

Use ``read_engine()`` for selects, ``write_engine()`` for writes, and
``session_factory()`` for ``async with sf() as session: ...`` blocks.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from merapy.config.env import Env
from merapy.logger import get_logger

logger = get_logger(__name__)


class SQLDatabaseImpl:
    __slots__ = ("_read", "_write", "_session_factory")

    def __init__(self, read_dsn: str, write_dsn: str, *, pool_size: int, max_overflow: int, echo: bool) -> None:
        self._read = create_async_engine(
            read_dsn, pool_size=pool_size, max_overflow=max_overflow, echo=echo, pool_pre_ping=True
        )
        self._write = (
            self._read
            if read_dsn == write_dsn
            else create_async_engine(
                write_dsn,
                pool_size=pool_size,
                max_overflow=max_overflow,
                echo=echo,
                pool_pre_ping=True,
            )
        )
        self._session_factory = async_sessionmaker(self._write, expire_on_commit=False)

    def read_engine(self) -> AsyncEngine:
        return self._read

    def write_engine(self) -> AsyncEngine:
        return self._write

    def session_factory(self) -> async_sessionmaker:
        return self._session_factory

    async def health(self) -> dict[str, str | None]:
        result: dict[str, str | None] = {"read": None, "write": None}
        for label, engine in (("read", self._read), ("write", self._write)):
            try:
                async with engine.connect() as conn:
                    await conn.execute(_health_stmt())
            except Exception as e:
                result[label] = str(e)
        return result

    async def close(self) -> None:
        await self._write.dispose()
        if self._read is not self._write:
            await self._read.dispose()


def _health_stmt() -> object:
    from sqlalchemy import text

    return text("SELECT 1")


def init_sql(env: Env) -> SQLDatabaseImpl | None:
    """Build the SQL engine pair, or return ``None`` if no DSN is configured."""
    if not env.sql_dsn_write:
        return None
    db = SQLDatabaseImpl(
        read_dsn=env.sql_dsn_read or env.sql_dsn_write,
        write_dsn=env.sql_dsn_write,
        pool_size=env.sql_pool_size,
        max_overflow=env.sql_max_overflow,
        echo=env.sql_echo,
    )
    # Instrument both engines for automatic SQL query tracing.
    # instrument_sql_database is a no-op if the tracer is not initialized.
    try:
        from merapy.tracer.sql_tracer import instrument_sql_database
        instrument_sql_database(db)
    except Exception:
        logger.warning("sql.tracer_instrument_failed")
    logger.info("sql.connected", read=bool(env.sql_dsn_read), write=True)
    return db
