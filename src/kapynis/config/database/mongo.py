"""MongoDB async client. Mirrors candi's ``config/database/mongo.go``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kapynis.config.env import Env
from kapynis.logger import get_logger

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

logger = get_logger(__name__)


class MongoDB:
    __slots__ = ("_read_client", "_write_client", "_read_db", "_write_db")

    def __init__(self, read_dsn: str, write_dsn: str, db_name: str) -> None:
        from motor.motor_asyncio import AsyncIOMotorClient

        self._read_client: AsyncIOMotorClient = AsyncIOMotorClient(read_dsn)
        self._write_client: AsyncIOMotorClient = (
            self._read_client if read_dsn == write_dsn else AsyncIOMotorClient(write_dsn)
        )
        self._read_db: AsyncIOMotorDatabase = self._read_client[db_name]
        self._write_db: AsyncIOMotorDatabase = self._write_client[db_name]

    def read_db(self) -> "AsyncIOMotorDatabase":
        return self._read_db

    def write_db(self) -> "AsyncIOMotorDatabase":
        return self._write_db

    async def health(self) -> dict[str, str | None]:
        result: dict[str, str | None] = {"read": None, "write": None}
        for label, client in (("read", self._read_client), ("write", self._write_client)):
            try:
                await client.admin.command("ping")
            except Exception as e:
                result[label] = str(e)
        return result

    async def close(self) -> None:
        self._write_client.close()
        if self._read_client is not self._write_client:
            self._read_client.close()


def init_mongo(env: Env) -> MongoDB | None:
    if not env.mongo_dsn_write or not env.mongo_db_name:
        return None
    db = MongoDB(
        read_dsn=env.mongo_dsn_read or env.mongo_dsn_write,
        write_dsn=env.mongo_dsn_write,
        db_name=env.mongo_db_name,
    )
    logger.info("mongo.connected", db=env.mongo_db_name)
    return db
