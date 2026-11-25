"""Standalone async task-queue worker engine."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from merapy_taskqueue.store.base import JobStore
from merapy_taskqueue.store.memory import MemoryJobStore
from merapy_taskqueue.types import (
    DashboardConfig,
    JobRecord,
    JobStatus,
    TaskContext,
    TaskSummary,
    utcnow,
)

logger = logging.getLogger(__name__)

TaskHandler = Callable[[TaskContext], Awaitable[Any]]
ErrorHook = Callable[[Exception], bool]


@dataclass(slots=True)
class RegisteredTask:
    name: str
    handler: TaskHandler
    module_name: str = "default"


class TaskQueue:
    """Standalone async task queue with pluggable ``JobStore`` and optional dashboard.

    Can be used directly in any Python project (FastAPI, Starlette, Django,
    or plain ``asyncio``) with zero dependency on the full ``merapy`` framework.
    """

    def __init__(
        self,
        store: JobStore | None = None,
        *,
        max_workers: int = 10,
        poll_interval: float = 1.0,
        batch_size: int = 50,
        dashboard_enabled: bool = True,
        dashboard_port: int = 8080,
        dashboard_host: str = "0.0.0.0",
        service_name: str = "",
        service_version: str = "",
        framework_version: str = "",
        build_number: str = "",
        git_commit: str = "",
        build_date: str = "",
        static_dir: str | None = None,
        on_fatal_error: ErrorHook | None = None,
    ) -> None:
        self._store: JobStore = store if store is not None else MemoryJobStore()
        self._max_workers = max(1, max_workers)
        self._poll_interval = max(0.05, poll_interval)
        self._batch_size = max(1, min(500, batch_size))
        self._dashboard_enabled = dashboard_enabled
        self._dashboard_config = DashboardConfig(
            host=dashboard_host,
            port=dashboard_port,
            service_name=service_name,
            service_version=service_version,
            framework_version=framework_version,
            build_number=build_number,
            git_commit=git_commit,
            build_date=build_date,
            static_dir=static_dir,
        )
        self._on_fatal_error = on_fatal_error
        self._tasks: dict[str, list[RegisteredTask]] = {}
        self._stop = asyncio.Event()
        self._semaphore: asyncio.Semaphore | None = None
        self._change_condition: asyncio.Condition | None = None
        self._dashboard_instance: Any = None

    @property
    def store(self) -> JobStore:
        return self._store

    @property
    def dashboard_config(self) -> DashboardConfig:
        return self._dashboard_config

    @property
    def registered_task_names(self) -> list[str]:
        return list(self._tasks.keys())

    def register(
        self,
        task_name: str,
        handler: TaskHandler,
        *,
        module_name: str = "default",
    ) -> None:
        """Register an async handler for ``task_name``."""
        clean_name = task_name.strip()
        if not clean_name:
            raise ValueError("task_name cannot be empty")
        self._tasks.setdefault(clean_name, []).append(
            RegisteredTask(name=clean_name, handler=handler, module_name=module_name)
        )

    def task(
        self,
        name: str | None = None,
        *,
        module_name: str = "default",
    ) -> Callable[[TaskHandler], TaskHandler]:
        """Decorator to register an async function as a task handler."""

        def decorator(fn: TaskHandler) -> TaskHandler:
            raw_name = name if name is not None else str(getattr(fn, "__name__", ""))
            task_name = raw_name.strip()
            self.register(task_name, fn, module_name=module_name)
            return fn

        return decorator

    def _get_condition(self) -> asyncio.Condition:
        if self._change_condition is None:
            self._change_condition = asyncio.Condition()
        return self._change_condition

    def notify_change(self) -> None:
        """Wake active dashboard subscribers so UI updates immediately."""

        async def _pulse() -> None:
            cond = self._get_condition()
            async with cond:
                cond.notify_all()

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_pulse())
        except RuntimeError:
            pass

    async def wait_for_change(self, timeout: float = 2.0) -> None:
        cond = self._get_condition()
        async with cond:
            try:
                await asyncio.wait_for(cond.wait(), timeout=timeout)
            except TimeoutError:
                pass

    async def enqueue(
        self,
        task_name: str,
        args: dict[str, Any] | str | bytes = "",
        *,
        max_retry: int = 5,
        interval: str = "",
    ) -> str:
        """Enqueue a new job and notify dashboard subscribers."""
        clean_name = task_name.strip()
        if not clean_name:
            raise ValueError("task_name cannot be empty")
        clamped_retry = max(1, min(100, int(max_retry)))
        if isinstance(args, dict):
            arguments = json.dumps(args)
        elif isinstance(args, bytes):
            arguments = args.decode("utf-8")
        else:
            arguments = str(args)

        now = utcnow()
        job = JobRecord(
            task_name=clean_name,
            arguments=arguments,
            max_retry=clamped_retry,
            interval=interval,
            status=JobStatus.QUEUEING,
            created_at=now,
            updated_at=now,
        )
        job_id = await self._store.enqueue(job)
        self.notify_change()
        return job_id

    async def get_task_summaries(self) -> list[TaskSummary]:
        """Return summaries for all registered tasks using the active ``JobStore``."""
        if not self._tasks:
            return []
        names = list(self._tasks.keys())
        counts_map = await self._store.get_summaries(names)
        summaries: list[TaskSummary] = []
        for name in names:
            entries = self._tasks[name]
            module_name = entries[0].module_name if entries else name
            summaries.append(
                TaskSummary(
                    name=name,
                    module_name=module_name,
                    counts=counts_map[name],
                )
            )
        return summaries

    async def tick(self) -> int:
        """Dequeue and execute one batch of ready jobs. Returns jobs processed."""
        if not self._tasks:
            return 0
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_workers)
        jobs = await self._store.dequeue_batch(self._tasks.keys(), limit=self._batch_size)
        if not jobs:
            return 0
        await asyncio.gather(*(self._run_job(job) for job in jobs))
        return len(jobs)

    async def _run_job(self, job: JobRecord) -> None:
        assert self._semaphore is not None
        entries = self._tasks.get(job.task_name, [])
        async with self._semaphore:
            ctx = TaskContext(
                job_id=job.id,
                task_name=job.task_name,
                arguments=job.arguments,
                retries=job.retries,
                max_retry=job.max_retry,
                interval=job.interval,
                headers={
                    "retries": str(job.retries),
                    "max_retry": str(job.max_retry),
                    "interval": job.interval,
                },
            )
            error_msg: str | None = None
            result_str = ""
            start_at = utcnow()
            for entry in entries:
                try:
                    ret = await entry.handler(ctx)
                    if ret is not None:
                        result_str = (
                            json.dumps(ret) if isinstance(ret, (dict, list)) else str(ret)
                        )
                except Exception as exc:
                    error_msg = str(exc)
                    logger.exception("task_queue.handler_failed task=%s job_id=%s", job.task_name, job.id)
                    break
            end_at = utcnow()
            await self._store.finish_job(
                job,
                error=error_msg,
                result=result_str,
                start_at=start_at,
                end_at=end_at,
            )
            self.notify_change()

    def dashboard_app(self) -> Any:
        """Build and return the mountable FastAPI dashboard application."""
        from merapy_taskqueue.dashboard import TaskQueueDashboard  # noqa: PLC0415

        return TaskQueueDashboard(self, config=self._dashboard_config).build_app()

    async def serve(self) -> None:
        """Run the polling worker loop alongside the optional live dashboard server."""
        self._stop.clear()
        self._semaphore = asyncio.Semaphore(self._max_workers)
        dashboard_task: asyncio.Task[None] | None = None

        if self._dashboard_enabled:
            from merapy_taskqueue.dashboard import TaskQueueDashboard  # noqa: PLC0415

            dashboard = TaskQueueDashboard(self, config=self._dashboard_config)
            self._dashboard_instance = dashboard
            dashboard_task = asyncio.create_task(dashboard.serve(), name="merapy-taskqueue-dashboard")

        try:
            if not self._tasks:
                logger.info("task_queue.no_handlers")
                await self._stop.wait()
                return

            await self._store.init_summaries(self._tasks.keys())

            while not self._stop.is_set():
                try:
                    processed = await self.tick()
                    if processed == 0:
                        try:
                            await asyncio.wait_for(self._stop.wait(), timeout=self._poll_interval)
                        except TimeoutError:
                            pass
                except Exception as exc:
                    if self._on_fatal_error is not None and self._on_fatal_error(exc):
                        self._stop.set()
                        return
                    logger.exception("task_queue.tick_failed")
                    await asyncio.sleep(self._poll_interval)
        finally:
            if self._dashboard_instance is not None:
                await self._dashboard_instance.shutdown()
            if dashboard_task is not None:
                dashboard_task.cancel()
                await asyncio.gather(dashboard_task, return_exceptions=True)
            await self._store.close()

    async def shutdown(self) -> None:
        """Signal the worker loop and dashboard server to stop gracefully."""
        self._stop.set()
        if self._dashboard_instance is not None:
            await self._dashboard_instance.shutdown()
