"""Merapy ``AppServerFactory`` adapter around standalone ``merapy-taskqueue``."""

from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING, Any

try:
    from merapy_taskqueue.store.memory import MemoryJobStore
    from merapy_taskqueue.store.sql import SQLJobStore
    from merapy_taskqueue.types import TaskContext
    from merapy_taskqueue.worker import TaskQueue
except ImportError as exc:
    raise ImportError(
        "merapy-taskqueue is required when USE_TASK_QUEUE_WORKER=true. "
        "Install it with: pip install 'merapy[taskqueue]' or pip install merapy-taskqueue[sql,metrics]"
    ) from exc

from merapy import __version__ as _merapy_version
from merapy.codebase.app._worker_base import collect_handlers
from merapy.codebase.app.task_queue_worker.dashboard import _find_static_dir
from merapy.codebase.factory.dependency import get_dependency
from merapy.codebase.types import EventContext, Worker, WorkerHandlerEntry
from merapy.logger import get_logger
from merapy.tracer import bind_trace_context, get_trace_id, get_trace_url, log_to_span, start_trace

if TYPE_CHECKING:
    from merapy.codebase.factory.service_factory import ServiceFactory

logger = get_logger(__name__)

_POLL_INTERVAL = 1.0


class TaskQueueWorker:
    """Merapy service worker wrapping standalone ``merapy_taskqueue.TaskQueue``."""

    name = "task-queue"

    __slots__ = ("_service", "_stop", "_handlers", "_semaphore", "_session_factory", "_queue")

    def __init__(self, service: ServiceFactory) -> None:
        self._service = service
        self._stop = asyncio.Event()
        self._handlers: dict[str, list[tuple[str, WorkerHandlerEntry]]] = {}
        self._semaphore: asyncio.Semaphore | None = None
        self._session_factory: Any = None
        self._queue: TaskQueue | None = None

    def _wrap_entry(
        self,
        module: str,
        entry: WorkerHandlerEntry,
        store: SQLJobStore,
    ) -> Any:
        async def _run_entry(tctx: TaskContext) -> None:
            ctx = EventContext(
                worker_type=Worker.TASK_QUEUE.value,
                handler_route=tctx.task_name,
                key=tctx.job_id,
                body=tctx.body,
                headers=tctx.headers,
            )
            if entry.disable_trace:
                await entry.handler(ctx)
                return

            async with start_trace(f"TaskQueue:{module}:{tctx.task_name}") as span:
                span.set_attribute("task.name", tctx.task_name)
                span.set_attribute("task.id", tctx.job_id)
                span.set_attribute("task.retries", tctx.retries)
                span.set_attribute("task.max_retry", tctx.max_retry)
                log_to_span("task.arguments", args=tctx.arguments)

                trace_id = get_trace_id()
                if trace_id:
                    await store.persist_trace_id(tctx.job_id, trace_id)

                bind_trace_context()
                await entry.handler(ctx)

            trace_url = get_trace_url()
            if trace_url:
                logger.info("task_queue > trace_url", url=trace_url)

        return _run_entry

    async def serve(self) -> None:
        env = self._service.config().env
        entries = collect_handlers(self._service, Worker.TASK_QUEUE)
        static_dir = _find_static_dir()

        sql_db = get_dependency().sql_db()
        mongo_db = get_dependency().mongo_db()

        if not entries or sql_db is None:
            if not entries:
                logger.info("task_queue.no_handlers")
            elif mongo_db is not None:
                logger.warning(
                    "task_queue.mongo_not_supported",
                    message=(
                        "Core SQL task queue worker requires SQL_DSN_WRITE in .env. "
                        "For MongoDB persistence, use merapy_taskqueue.MongoJobStore."
                    ),
                )
            else:
                logger.error("task_queue.no_persistent — requires SQL_DSN_WRITE in .env")

            # Keep dashboard reachable even when no handlers or DB are wired.
            idle_queue = TaskQueue(
                store=MemoryJobStore(),
                dashboard_enabled=True,
                dashboard_port=env.task_queue_dashboard_port,
                service_name=env.service_name,
                service_version=env.app_version,
                framework_version=_merapy_version,
                build_number=env.build_number,
                git_commit=env.git_commit,
                build_date=env.build_date,
                static_dir=str(static_dir) if static_dir is not None else None,
            )
            self._queue = idle_queue
            await idle_queue.serve()
            return

        self._session_factory = sql_db.session_factory()
        store = SQLJobStore(self._session_factory)
        logger.info("task_queue.persistent", backend="sql")

        def _handle_fatal(exc: Exception) -> bool:
            if _is_missing_table(exc):
                _print_missing_table_guide()
                return True
            return False

        queue = TaskQueue(
            store=store,
            max_workers=env.max_workers,
            poll_interval=_POLL_INTERVAL,
            dashboard_enabled=True,
            dashboard_port=env.task_queue_dashboard_port,
            service_name=env.service_name,
            service_version=env.app_version,
            framework_version=_merapy_version,
            build_number=env.build_number,
            git_commit=env.git_commit,
            build_date=env.build_date,
            static_dir=str(static_dir) if static_dir is not None else None,
            on_fatal_error=_handle_fatal,
        )
        self._queue = queue

        for module, entry in entries:
            self._handlers.setdefault(entry.pattern, []).append((module, entry))
            queue.register(
                entry.pattern,
                self._wrap_entry(module, entry, store),
                module_name=module,
            )

        logger.info(
            "task_queue.handlers",
            names=list(self._handlers.keys()),
            dashboard=f"http://localhost:{env.task_queue_dashboard_port}",
        )
        await queue.serve()

    async def shutdown(self) -> None:
        self._stop.set()
        if self._queue is not None:
            await self._queue.shutdown()


def _is_missing_table(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "does not exist" in msg or "undefinedtable" in msg or "no such table" in msg


def _print_missing_table_guide() -> None:
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
