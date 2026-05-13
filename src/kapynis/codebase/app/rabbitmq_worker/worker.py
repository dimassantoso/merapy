"""RabbitMQ consumer worker (aio-pika).

Each handler ``pattern`` is the queue name. The worker connects, declares
each queue (durable, no-auto-delete), and starts an ``iterator`` consumer
per queue. Messages are dispatched to all handlers registered for that queue,
acked once handlers return successfully.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import aio_pika

from kapynis.codebase.app._worker_base import collect_handlers
from kapynis.codebase.types import EventContext, Worker, WorkerHandlerEntry
from kapynis.logger import get_logger
from kapynis.tracer import start_trace

if TYPE_CHECKING:
    from kapynis.codebase.factory.service_factory import ServiceFactory

logger = get_logger(__name__)


class RabbitMQWorker:
    name = "rabbitmq"

    __slots__ = ("_service", "_stop", "_connection", "_channel", "_tasks", "_semaphore")

    def __init__(self, service: "ServiceFactory") -> None:
        self._service = service
        self._stop = asyncio.Event()
        self._connection: aio_pika.abc.AbstractConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._semaphore: asyncio.Semaphore | None = None

    async def serve(self) -> None:
        env = self._service.config().env
        entries = collect_handlers(self._service, Worker.RABBITMQ)
        if not entries:
            logger.info("rabbitmq.no_handlers")
            await self._stop.wait()
            return
        if not env.rabbitmq.broker:
            logger.error("rabbitmq.no_url")
            await self._stop.wait()
            return

        self._semaphore = asyncio.Semaphore(env.max_workers)
        try:
            self._connection = await asyncio.wait_for(
                aio_pika.connect_robust(env.rabbitmq.broker), timeout=10.0
            )
        except (asyncio.TimeoutError, Exception) as exc:
            logger.error("rabbitmq.connect_failed", error=str(exc), broker=env.rabbitmq.broker)
            await self._stop.wait()
            return
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=env.max_workers)
        logger.info(
            "rabbitmq.connected",
            broker=env.rabbitmq.broker,
            queues=[e.pattern for _, e in entries],
        )

        # Group handlers by queue.
        queue_handlers: dict[str, list[tuple[str, WorkerHandlerEntry]]] = {}
        for module, entry in entries:
            queue_handlers.setdefault(entry.pattern, []).append((module, entry))

        for queue_name, handlers in queue_handlers.items():
            queue = await self._channel.declare_queue(queue_name, durable=True)
            self._tasks.append(
                asyncio.create_task(self._consume(queue, handlers), name=f"rabbitmq:{queue_name}")
            )
        await self._stop.wait()

    async def _consume(
        self,
        queue: aio_pika.abc.AbstractQueue,
        handlers: list[tuple[str, WorkerHandlerEntry]],
    ) -> None:
        async with queue.iterator() as it:
            async for message in it:
                if self._stop.is_set():
                    return
                await self._dispatch(message, handlers)

    async def _dispatch(
        self,
        message: aio_pika.abc.AbstractIncomingMessage,
        handlers: list[tuple[str, WorkerHandlerEntry]],
    ) -> None:
        assert self._semaphore is not None
        async with self._semaphore:
            ctx = EventContext(
                worker_type=Worker.RABBITMQ.value,
                handler_route=message.routing_key or "",
                key=message.message_id or "",
                body=message.body,
                headers={k: str(v) for k, v in (message.headers or {}).items()},
            )
            any_failed = False
            for module, entry in handlers:
                try:
                    if entry.disable_trace:
                        await entry.handler(ctx)
                    else:
                        async with start_trace(f"RabbitMQ:{module}:{entry.pattern}") as span:
                            span.set_attribute("queue", entry.pattern)
                            span.set_attribute("module", module)
                            await entry.handler(ctx)
                except Exception:
                    any_failed = True
                    logger.exception("rabbitmq.handler_failed", module=module, queue=entry.pattern)
            if any_failed:
                await message.nack(requeue=True)
            else:
                await message.ack()

    async def shutdown(self) -> None:
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        if self._channel is not None:
            await self._channel.close()
        if self._connection is not None:
            await self._connection.close()
