"""Postgres LISTEN/NOTIFY worker.

Each handler ``pattern`` is the NOTIFY channel name. Uses ``asyncpg``
directly (lighter than going through SQLAlchemy for LISTEN). One connection
listens to all channels; payload is delivered as the EventContext body.

Candi exposes a higher-level "table change notification" mode that creates
triggers per table. That's deferred for v1 — register your own triggers
and use this worker to receive their notifications.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from merapy.codebase.app._worker_base import collect_handlers
from merapy.codebase.types import EventContext, Worker, WorkerHandlerEntry
from merapy.logger import get_logger
from merapy.tracer import start_trace

if TYPE_CHECKING:
    from merapy.codebase.factory.service_factory import ServiceFactory

logger = get_logger(__name__)


def _dsn_to_asyncpg(dsn: str) -> str:
    """Strip SQLAlchemy ``+asyncpg`` suffix if present."""
    return dsn.replace("postgresql+asyncpg://", "postgresql://", 1)


class PostgresListenerWorker:
    name = "postgres-listener"

    __slots__ = ("_service", "_stop", "_conn", "_handlers", "_queue", "_loop_task")

    def __init__(self, service: "ServiceFactory") -> None:
        self._service = service
        self._stop = asyncio.Event()
        self._conn: object | None = None
        self._handlers: dict[str, list[tuple[str, WorkerHandlerEntry]]] = {}
        self._queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
        self._loop_task: asyncio.Task[None] | None = None

    async def serve(self) -> None:
        try:
            import asyncpg
        except ImportError:
            logger.error("postgres_listener.asyncpg_missing")
            await self._stop.wait()
            return

        env = self._service.config().env
        entries = collect_handlers(self._service, Worker.POSTGRES_LISTENER)
        if not entries:
            logger.info("postgres_listener.no_handlers")
            await self._stop.wait()
            return
        if not env.sql_dsn_write:
            logger.error("postgres_listener.no_dsn")
            await self._stop.wait()
            return

        for module, entry in entries:
            self._handlers.setdefault(entry.pattern, []).append((module, entry))

        self._conn = await asyncpg.connect(_dsn_to_asyncpg(env.sql_dsn_write))
        for channel in self._handlers:
            await self._conn.add_listener(channel, self._on_notify)  # type: ignore[attr-defined]
        logger.info("postgres_listener.listening", channels=list(self._handlers.keys()))

        self._loop_task = asyncio.create_task(self._loop(), name="pg-listen")
        await self._stop.wait()

    def _on_notify(self, _conn: object, _pid: int, channel: str, payload: str) -> None:
        try:
            self._queue.put_nowait((channel, payload))
        except asyncio.QueueFull:
            logger.warning("postgres_listener.queue_full", channel=channel)

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                channel, payload = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            for module, entry in self._handlers.get(channel, []):
                ctx = EventContext(
                    worker_type=Worker.POSTGRES_LISTENER.value,
                    handler_route=channel,
                    body=payload.encode(),
                )
                try:
                    if entry.disable_trace:
                        await entry.handler(ctx)
                    else:
                        async with start_trace(f"PgListen:{module}:{channel}") as span:
                            span.set_attribute("channel", channel)
                            span.set_attribute("module", module)
                            await entry.handler(ctx)
                except Exception:
                    logger.exception(
                        "postgres_listener.handler_failed", module=module, channel=channel
                    )

    async def shutdown(self) -> None:
        self._stop.set()
        if self._loop_task is not None:
            self._loop_task.cancel()
            await asyncio.gather(self._loop_task, return_exceptions=True)
        if self._conn is not None:
            try:
                await self._conn.close()  # type: ignore[attr-defined]
            except Exception:
                pass
