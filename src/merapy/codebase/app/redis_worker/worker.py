"""Redis pub/sub subscriber worker.

Each handler ``pattern`` is a channel name. Use a ``*`` suffix for
``PSUBSCRIBE`` semantics (e.g. ``events:*``).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from merapy.codebase.app._worker_base import collect_handlers
from merapy.codebase.factory.dependency import get_dependency
from merapy.codebase.types import EventContext, Worker, WorkerHandlerEntry
from merapy.logger import get_logger
from merapy.tracer import start_trace

if TYPE_CHECKING:
    from merapy.codebase.factory.service_factory import ServiceFactory

logger = get_logger(__name__)


class RedisWorker:
    name = "redis-subscriber"

    __slots__ = ("_service", "_stop", "_pubsub", "_task", "_semaphore", "_handlers")

    def __init__(self, service: "ServiceFactory") -> None:
        self._service = service
        self._stop = asyncio.Event()
        self._pubsub: object | None = None
        self._task: asyncio.Task[None] | None = None
        self._semaphore: asyncio.Semaphore | None = None
        self._handlers: dict[str, list[tuple[str, WorkerHandlerEntry]]] = {}

    async def serve(self) -> None:
        env = self._service.config().env
        entries = collect_handlers(self._service, Worker.REDIS_SUBSCRIBER)
        if not entries:
            logger.info("redis_sub.no_handlers")
            await self._stop.wait()
            return

        pool = get_dependency().redis_pool()
        if pool is None:
            logger.error("redis_sub.no_pool")
            await self._stop.wait()
            return

        for module, entry in entries:
            self._handlers.setdefault(entry.pattern, []).append((module, entry))

        self._semaphore = asyncio.Semaphore(env.max_workers)
        client = pool.read()
        self._pubsub = client.pubsub()
        channels = [p for p in self._handlers if not p.endswith("*")]
        patterns = [p for p in self._handlers if p.endswith("*")]
        if channels:
            await self._pubsub.subscribe(*channels)  # type: ignore[attr-defined]
        if patterns:
            await self._pubsub.psubscribe(*patterns)  # type: ignore[attr-defined]

        logger.info("redis_sub.subscribed", channels=channels, patterns=patterns)
        self._task = asyncio.create_task(self._loop(), name="redis-sub")
        await self._stop.wait()

    async def _loop(self) -> None:
        assert self._pubsub is not None
        while not self._stop.is_set():
            try:
                msg = await asyncio.wait_for(
                    self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),  # type: ignore[attr-defined]
                    timeout=2.0,
                )
            except asyncio.TimeoutError:
                continue
            if msg is None:
                continue
            await self._dispatch(msg)

    async def _dispatch(self, msg: dict[str, object]) -> None:
        assert self._semaphore is not None
        channel = (msg.get("channel") or b"").decode() if isinstance(msg.get("channel"), bytes) else str(msg.get("channel") or "")
        pattern = (msg.get("pattern") or b"").decode() if isinstance(msg.get("pattern"), bytes) else str(msg.get("pattern") or "")
        body_raw = msg.get("data") or b""
        body = body_raw if isinstance(body_raw, bytes) else str(body_raw).encode()

        key = pattern or channel
        handlers = self._handlers.get(key) or self._handlers.get(channel) or []
        if not handlers:
            return

        async with self._semaphore:
            ctx = EventContext(
                worker_type=Worker.REDIS_SUBSCRIBER.value,
                handler_route=channel,
                key=key,
                body=body,
            )
            for module, entry in handlers:
                try:
                    if entry.disable_trace:
                        await entry.handler(ctx)
                    else:
                        async with start_trace(f"RedisSub:{module}:{entry.pattern}") as span:
                            span.set_attribute("channel", channel)
                            span.set_attribute("module", module)
                            await entry.handler(ctx)
                except Exception:
                    logger.exception("redis_sub.handler_failed", module=module, channel=channel)

    async def shutdown(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        if self._pubsub is not None:
            try:
                await self._pubsub.aclose()  # type: ignore[attr-defined]
            except Exception:
                pass
