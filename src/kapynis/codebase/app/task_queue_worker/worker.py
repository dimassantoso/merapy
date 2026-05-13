"""Poll-based task-queue worker.

Uses the same table schema as candi's task_queue_worker so the
kapynis-taskqueue-dashboard can connect to either implementation.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select, update, text

from kapynis.codebase.app._worker_base import collect_handlers
from kapynis.codebase.app.task_queue_worker.model import (
    Job, JobHistory, JobStatus, JobSummary, TaskQueueBase,
)
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

        logger.info(
            "task_queue.handlers",
            names=list(self._handlers.keys()),
            dashboard=f"http://localhost:{env.task_queue_dashboard_port}",
        )

        # Start the dashboard server alongside the poll loop.
        from kapynis.codebase.app.task_queue_worker.dashboard import TaskQueueDashboard
        dashboard = TaskQueueDashboard(self, port=env.task_queue_dashboard_port)
        dashboard_task = asyncio.create_task(dashboard.serve(), name="task-queue-dashboard")

        try:
            while not self._stop.is_set():
                try:
                    processed = await self._tick()
                    if processed == 0:
                        try:
                            await asyncio.wait_for(self._stop.wait(), timeout=_POLL_INTERVAL)
                        except asyncio.TimeoutError:
                            pass
                except Exception as exc:
                    if _is_missing_table(exc):
                        _print_missing_table_guide()
                        self._stop.set()
                        return
                    logger.exception("task_queue.tick_failed")
                    await asyncio.sleep(_POLL_INTERVAL)
        finally:
            dashboard_task.cancel()
            await asyncio.gather(dashboard_task, return_exceptions=True)

    async def _tick(self) -> int:
        assert self._session_factory is not None
        assert self._semaphore is not None
        now = datetime.now(tz=timezone.utc)
        async with self._session_factory() as session:  # type: ignore[misc]
            async with session.begin():
                stmt = (
                    select(Job)
                    .where(
                        Job.status == JobStatus.QUEUEING,
                        Job.task_name.in_(self._handlers.keys()),
                    )
                    .order_by(Job.created_at.asc())
                    .limit(50)
                    .with_for_update(skip_locked=True)
                )
                result = await session.execute(stmt)
                jobs = list(result.scalars().all())
                if not jobs:
                    return 0
                ids = [j.id for j in jobs]
                await session.execute(
                    update(Job)
                    .where(Job.id.in_(ids))
                    .values(status=JobStatus.RETRYING, updated_at=now)
                )
        await asyncio.gather(*(self._run(j) for j in jobs))
        return len(jobs)

    async def _run(self, job: Job) -> None:
        assert self._session_factory is not None
        assert self._semaphore is not None
        handlers = self._handlers.get(job.task_name, [])
        async with self._semaphore:
            ctx = EventContext(
                worker_type=Worker.TASK_QUEUE.value,
                handler_route=job.task_name,
                key=job.id,
                body=job.arguments.encode(),
                headers={
                    "retries": str(job.retries),
                    "max_retry": str(job.max_retry),
                    "interval": job.interval,
                },
            )
            error: Exception | None = None
            start_at = datetime.now(tz=timezone.utc)
            for module, entry in handlers:
                try:
                    if entry.disable_trace:
                        await entry.handler(ctx)
                    else:
                        async with start_trace(f"TaskQueue:{module}:{job.task_name}") as span:
                            span.set_attribute("task.name", job.task_name)
                            span.set_attribute("task.id", job.id)
                            await entry.handler(ctx)
                except Exception as e:
                    error = e
                    logger.exception(
                        "task_queue.handler_failed", module=module, task=job.task_name
                    )
                    break
            await self._finalize(job, error, start_at)

    async def _finalize(
        self, job: Job, error: Exception | None, start_at: datetime
    ) -> None:
        assert self._session_factory is not None
        now = datetime.now(tz=timezone.utc)
        new_retries = job.retries + 1

        async with self._session_factory() as session:  # type: ignore[misc]
            async with session.begin():
                session.add(
                    JobHistory(
                        job_id=job.id,
                        status=JobStatus.SUCCESS if error is None else JobStatus.FAILURE,
                        error=str(error) if error else "",
                        start_at=start_at,
                        end_at=now,
                    )
                )
                if error is None:
                    await session.execute(
                        update(Job).where(Job.id == job.id).values(
                            status=JobStatus.SUCCESS,
                            finished_at=now,
                            updated_at=now,
                            retries=new_retries,
                            error="",
                        )
                    )
                    await _upsert_summary(session, job.task_name, JobStatus.SUCCESS)
                elif new_retries >= job.max_retry:
                    await session.execute(
                        update(Job).where(Job.id == job.id).values(
                            status=JobStatus.FAILURE,
                            finished_at=now,
                            updated_at=now,
                            retries=new_retries,
                            error=str(error),
                        )
                    )
                    await _upsert_summary(session, job.task_name, JobStatus.FAILURE)
                else:
                    backoff = timedelta(seconds=min(60, 2**new_retries))
                    await session.execute(
                        update(Job).where(Job.id == job.id).values(
                            status=JobStatus.QUEUEING,
                            updated_at=now,
                            retries=new_retries,
                            error=str(error),
                            finished_at=None,
                        )
                    )
                    await _upsert_summary(session, job.task_name, JobStatus.RETRYING)

    async def shutdown(self) -> None:
        self._stop.set()


async def _upsert_summary(session: object, task_name: str, status: str) -> None:
    col_map = {
        JobStatus.SUCCESS: "success",
        JobStatus.FAILURE: "failure",
        JobStatus.RETRYING: "retrying",
        JobStatus.QUEUEING: "queueing",
        JobStatus.STOPPED: "stopped",
    }
    col = col_map.get(status)
    if not col:
        return
    await session.execute(  # type: ignore[attr-defined]
        text(
            f"INSERT INTO task_queue_worker_job_summaries (id, {col}) "
            f"VALUES (:task_name, 1) "
            f"ON CONFLICT (id) DO UPDATE "
            f"SET {col} = task_queue_worker_job_summaries.{col} + 1"
        ),
        {"task_name": task_name},
    )


def _is_missing_table(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "does not exist" in msg or "undefinedtable" in msg or "no such table" in msg


def _print_missing_table_guide() -> None:
    import sys
    print(
        "\n"
        "\033[31m✗ Task queue worker failed: task queue tables do not exist.\033[0m\n"
        "\n"
        "  The task queue requires its own database tables.\n"
        "  Follow these steps:\n"
        "\n"
        "  \033[1m1. Create a migration file:\033[0m\n"
        "     make migration-create name=add_task_queue_tables\n"
        "\n"
        "  \033[1m2. Apply the migration:\033[0m\n"
        "     make migration\n"
        "\n"
        "  \033[1m3. Start the service again:\033[0m\n"
        "     make run\n",
        file=sys.stderr,
    )
