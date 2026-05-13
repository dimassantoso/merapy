"""Kafka consumer-group worker.

One process-wide ``AIOKafkaConsumer`` subscribes to all topics registered
by any module's Kafka handler. Messages are dispatched to the handler whose
pattern equals the topic name, with concurrency capped by ``MAX_WORKERS``.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from aiokafka import AIOKafkaConsumer

from kapynis.codebase.app._worker_base import collect_handlers
from kapynis.codebase.types import EventContext, Worker, WorkerHandlerEntry
from kapynis.logger import get_logger
from kapynis.tracer import start_trace

if TYPE_CHECKING:
    from kapynis.codebase.factory.service_factory import ServiceFactory

logger = get_logger(__name__)


class KafkaWorker:
    name = "kafka"

    __slots__ = ("_service", "_stop", "_consumer", "_dispatch_tasks", "_semaphore")

    def __init__(self, service: "ServiceFactory") -> None:
        self._service = service
        self._stop = asyncio.Event()
        self._consumer: AIOKafkaConsumer | None = None
        self._dispatch_tasks: set[asyncio.Task[None]] = set()
        self._semaphore: asyncio.Semaphore | None = None

    async def serve(self) -> None:
        env = self._service.config().env
        entries = collect_handlers(self._service, Worker.KAFKA)
        if not entries:
            logger.info("kafka.no_handlers")
            await self._stop.wait()
            return

        topic_handlers: dict[str, list[tuple[str, WorkerHandlerEntry]]] = {}
        for module, entry in entries:
            topic_handlers.setdefault(entry.pattern, []).append((module, entry))

        self._semaphore = asyncio.Semaphore(env.max_workers)
        self._consumer = AIOKafkaConsumer(
            *topic_handlers.keys(),
            bootstrap_servers=env.kafka.brokers,
            group_id=env.kafka.consumer_group or None,
            client_id=env.kafka.client_id or None,
            enable_auto_commit=False,
        )
        try:
            await asyncio.wait_for(self._consumer.start(), timeout=10.0)
        except (asyncio.TimeoutError, Exception) as exc:
            logger.error("kafka.connect_failed", error=str(exc), brokers=env.kafka.brokers)
            try:
                await self._consumer.stop()
            except Exception:
                pass
            self._consumer = None
            await self._stop.wait()
            return
        logger.info("kafka.subscribed", topics=list(topic_handlers.keys()))

        try:
            while not self._stop.is_set():
                try:
                    batch = await asyncio.wait_for(
                        self._consumer.getmany(timeout_ms=500), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                for _tp, msgs in batch.items():
                    for msg in msgs:
                        await self._dispatch(topic_handlers, msg)
                await self._consumer.commit()
        except asyncio.CancelledError:
            # Task was cancelled externally — drain then re-raise so the
            # orchestrator knows the task finished cleanly.
            logger.info("kafka.cancelled")
            raise
        finally:
            await self._drain()

    async def _dispatch(
        self,
        topic_handlers: dict[str, list[tuple[str, WorkerHandlerEntry]]],
        msg: object,
    ) -> None:
        assert self._semaphore is not None
        topic = msg.topic  # type: ignore[attr-defined]
        key = msg.key.decode() if msg.key else ""  # type: ignore[attr-defined]
        body = msg.value or b""  # type: ignore[attr-defined]
        raw_headers = msg.headers or []  # type: ignore[attr-defined]
        headers = {
            k: v.decode() if isinstance(v, (bytes, bytearray)) else str(v)
            for k, v in raw_headers
        }

        for module, entry in topic_handlers.get(topic, []):
            ctx = EventContext(
                worker_type=Worker.KAFKA.value,
                handler_route=topic,
                key=key,
                body=body,
                headers=headers,
            )
            task = asyncio.create_task(self._run(module, entry, ctx))
            self._dispatch_tasks.add(task)
            task.add_done_callback(self._dispatch_tasks.discard)

    async def _run(self, module: str, entry: WorkerHandlerEntry, ctx: EventContext) -> None:
        assert self._semaphore is not None
        async with self._semaphore:
            if entry.disable_trace:
                await self._safe(module, entry, ctx)
                return
            async with start_trace(f"Kafka:{module}:{entry.pattern}") as span:
                span.set_attribute("kafka.topic", entry.pattern)
                span.set_attribute("module", module)
                await self._safe(module, entry, ctx)

    async def _safe(self, module: str, entry: WorkerHandlerEntry, ctx: EventContext) -> None:
        try:
            await entry.handler(ctx)
        except Exception:
            logger.exception("kafka.handler_failed", module=module, topic=entry.pattern)

    async def _drain(self) -> None:
        """Drain in-flight dispatch tasks then stop the consumer."""
        if self._dispatch_tasks:
            await asyncio.gather(*self._dispatch_tasks, return_exceptions=True)
            self._dispatch_tasks.clear()
        if self._consumer is not None:
            try:
                await self._consumer.stop()
            except Exception:
                logger.exception("kafka.consumer_stop_failed")
            finally:
                self._consumer = None

    async def shutdown(self) -> None:
        """Signal the serve loop to stop and eagerly close the consumer.

        Called by the orchestrator with a deadline. Setting ``_stop`` causes
        the poll loop to exit on the next iteration. We also stop the consumer
        directly here so that if ``serve()`` is blocked inside ``getmany``
        the consumer is closed and the await unblocks immediately.
        """
        self._stop.set()
        if self._consumer is not None:
            try:
                await self._consumer.stop()
            except Exception:
                pass
            finally:
                self._consumer = None
