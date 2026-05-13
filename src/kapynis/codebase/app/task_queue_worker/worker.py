"""Poll-based task-queue worker."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select, update

from kapynis.codebase.app._worker_base import collect_handlers
from kapynis.codebase.app.task_queue_worker.model import Task, TaskStatus
from kapynis.codebase.factory.dependency import get_dependency
from kapynis.codebase.types import EventContext, Worker, WorkerHandlerEntry
from kapynis.logger import get_logger
from kapynis.tracer import start_trace

if TYPE_CHECKING:
    from kapynis.codebase.factory.service_factory import ServiceFactory

logger = get_logger(__name__)

_POLL_INTERVAL = 1.0


class TaskQueueWorker:
    name = "task-queue"

    __slots__ = ("_service", "_stop", "_handlers", "_semaphore", "_session_factory")

    def __init__(self, service: "ServiceFactory") -> None:
        self._service = service
        self._stop = asyncio.Event()
        self._handlers: dict[str, list[tuple[str, WorkerHandlerEntry]]] = {}
        self._semaphore: asyncio.Semaphore | None = None
        self._session_factory: object | None = None

    async def serve(self) -> None:
        env = self._service.config().env
        entries = collect_handlers(self._service, Worker.TASK_QUEUE)
        if not entries:
            logger.info("task_queue.no_handlers")
            await self._stop.wait()
            return

        sql_db = get_dependency().sql_db()
        if sql_db is None:
            logger.error("task_queue.no_sql_db")
            await self._stop.wait()
            return

        self._session_factory = sql_db.session_factory()
        self._semaphore = asyncio.Semaphore(env.max_workers)
        for module, entry in entries:
            self._handlers.setdefault(entry.pattern, []).append((module, entry))

        logger.info("task_queue.handlers", names=list(self._handlers.keys()))

        while not self._stop.is_set():
            try:
                processed = await self._tick()
                if processed == 0:
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=_POLL_INTERVAL)
                    except asyncio.TimeoutError:
                        pass
            except Exception:
                logger.exception("task_queue.tick_failed")
                await asyncio.sleep(_POLL_INTERVAL)

    async def _tick(self) -> int:
        assert self._session_factory is not None
        assert self._semaphore is not None
        now = datetime.now(tz=timezone.utc)
        async with self._session_factory() as session:  # type: ignore[misc]
            async with session.begin():
                stmt = (
                    select(Task)
                    .where(
                        Task.status == TaskStatus.PENDING,
                        Task.scheduled_at <= now,
                        Task.name.in_(self._handlers.keys()),
                    )
                    .order_by(Task.scheduled_at.asc())
                    .limit(50)
                    .with_for_update(skip_locked=True)
                )
                result = await session.execute(stmt)
                tasks = list(result.scalars().all())
                if not tasks:
                    return 0
                ids = [t.id for t in tasks]
                await session.execute(
                    update(Task)
                    .where(Task.id.in_(ids))
                    .values(status=TaskStatus.RUNNING, started_at=now)
                )
        # Run handlers outside the locking transaction.
        await asyncio.gather(*(self._run(t) for t in tasks))
        return len(tasks)

    async def _run(self, task: Task) -> None:
        assert self._session_factory is not None
        assert self._semaphore is not None
        handlers = self._handlers.get(task.name, [])
        async with self._semaphore:
            ctx = EventContext(
                worker_type=Worker.TASK_QUEUE.value,
                handler_route=task.name,
                key=str(task.id),
                body=task.payload,
            )
            error: Exception | None = None
            for module, entry in handlers:
                try:
                    if entry.disable_trace:
                        await entry.handler(ctx)
                    else:
                        async with start_trace(f"TaskQueue:{module}:{task.name}") as span:
                            span.set_attribute("task.name", task.name)
                            span.set_attribute("task.id", task.id)
                            await entry.handler(ctx)
                except Exception as e:
                    error = e
                    logger.exception("task_queue.handler_failed", module=module, task=task.name)
                    break
            await self._finalize(task, error)

    async def _finalize(self, task: Task, error: Exception | None) -> None:
        assert self._session_factory is not None
        now = datetime.now(tz=timezone.utc)
        async with self._session_factory() as session:  # type: ignore[misc]
            async with session.begin():
                if error is None:
                    await session.execute(
                        update(Task)
                        .where(Task.id == task.id)
                        .values(status=TaskStatus.DONE, finished_at=now, last_error=None)
                    )
                else:
                    attempts = task.attempts + 1
                    if attempts >= task.max_attempts:
                        await session.execute(
                            update(Task)
                            .where(Task.id == task.id)
                            .values(
                                status=TaskStatus.FAILED,
                                finished_at=now,
                                attempts=attempts,
                                last_error=str(error),
                            )
                        )
                    else:
                        backoff = timedelta(seconds=min(60, 2**attempts))
                        await session.execute(
                            update(Task)
                            .where(Task.id == task.id)
                            .values(
                                status=TaskStatus.PENDING,
                                attempts=attempts,
                                scheduled_at=now + backoff,
                                last_error=str(error),
                                started_at=None,
                            )
                        )

    async def shutdown(self) -> None:
        self._stop.set()
