"""Task Queue Worker Dashboard server.

Serves two things on ``TASK_QUEUE_DASHBOARD_PORT`` (default 8080):

1. ``/graphql``  — GraphQL API the dashboard JS calls (queries + mutations)
2. ``/``         — Static Next.js dashboard UI (built from merapy-taskqueue-dashboard)

The static files are looked up in this order:
  a. ``MERAPY_DASHBOARD_DIR`` env var (absolute path)
  b. ``<service_root>/dashboard/`` — user can copy the built ``out/`` folder here
  c. Bundled fallback inside merapy package (if shipped)

If no static files are found, only the GraphQL API is served and the root
returns a plain JSON health response.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncGenerator, Optional

import strawberry
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from strawberry.fastapi import GraphQLRouter
from sqlalchemy import func, select, update, delete, text

if TYPE_CHECKING:
    from merapy.codebase.app.task_queue_worker.worker import TaskQueueWorker


# ---------------------------------------------------------------------------
# GraphQL types
# ---------------------------------------------------------------------------

@strawberry.type
class MetaType:
    page: int
    limit: int
    total_pages: int
    total_records: int
    message: str = ""
    is_close_session: bool = False
    is_loading: bool = False


@strawberry.type
class JobResolver:
    id: str
    task_name: str
    arguments: str
    retries: int
    max_retry: int
    interval: str = ""
    error: str = ""
    result: str = ""
    trace_id: str = ""
    status: str = ""
    created_at: str = ""
    finished_at: str = ""


@strawberry.type
class JobListResolver:
    meta: MetaType
    data: list[JobResolver]


@strawberry.input
class GetAllJobInputResolver:
    page: Optional[int] = 1
    limit: Optional[int] = 20
    task_name: Optional[str] = None
    search: Optional[str] = None
    statuses: Optional[list[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    job_id: Optional[str] = None


@strawberry.input
class AddJobInputResolver:
    task_name: str
    max_retry: int
    args: str
    retry_interval: Optional[str] = None


@strawberry.input
class FilterMutateJobInputResolver:
    task_name: str
    search: Optional[str] = None
    job_id: Optional[str] = None
    statuses: list[str] = strawberry.field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None


# ---------------------------------------------------------------------------
# Worker stats
# ---------------------------------------------------------------------------

@strawberry.type
class WorkerStatsResolver:
    """Process memory and CPU snapshot for the running worker."""
    memory_rss_mb: float = 0.0
    """Resident Set Size — physical RAM used (MB)."""
    memory_vms_mb: float = 0.0
    """Virtual Memory Size (MB)."""
    memory_percent: float = 0.0
    """RSS as % of total system RAM."""
    cpu_percent: float = 0.0
    """CPU usage % since last call (non-blocking)."""
    merapy_version: str = ""
    """merapy framework version."""
    service_name: str = ""
    """Service name — read from SERVICE_NAME env var."""
    service_version: str = ""
    """Service version — read from APP_VERSION env var."""
    build_number: str = ""
    """CI build number — read from BUILD_NUMBER env var."""
    git_commit: str = ""
    """Git commit SHA — read from GIT_COMMIT env var."""
    build_date: str = ""
    """Build timestamp — read from BUILD_DATE env var."""


def _get_worker_stats() -> WorkerStatsResolver:
    """Collect process stats. Uses psutil if available, falls back to stdlib resource."""
    from merapy import __version__ as _merapy_version
    from merapy.config.env import get_env
    _env = get_env()
    service_name = _env.service_name
    service_version = _env.app_version
    build_number = _env.build_number
    git_commit = _env.git_commit
    build_date = _env.build_date

    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem = proc.memory_info()
        return WorkerStatsResolver(
            memory_rss_mb=round(mem.rss / 1024 / 1024, 2),
            memory_vms_mb=round(mem.vms / 1024 / 1024, 2),
            memory_percent=round(proc.memory_percent(), 2),
            cpu_percent=round(proc.cpu_percent(interval=None), 2),
            merapy_version=_merapy_version,
            service_name=service_name,
            service_version=service_version,
            build_number=build_number,
            git_commit=git_commit,
            build_date=build_date,
        )
    except ImportError:
        pass
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF)
        # ru_maxrss is in bytes on Linux, kilobytes on macOS
        import sys
        rss_bytes = usage.ru_maxrss * (1 if sys.platform == "linux" else 1024)
        return WorkerStatsResolver(
            memory_rss_mb=round(rss_bytes / 1024 / 1024, 2),
            merapy_version=_merapy_version,
            service_name=service_name,
            service_version=service_version,
            build_number=build_number,
            git_commit=git_commit,
            build_date=build_date,
        )
    except Exception:
        pass
    return WorkerStatsResolver(
        merapy_version=_merapy_version,
        service_name=service_name,
        service_version=service_version,
        build_number=build_number,
        git_commit=git_commit,
        build_date=build_date,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(dt: datetime | None) -> str:
    return dt.isoformat() if dt else ""


async def _query_jobs(
    session_factory: Any,
    f: GetAllJobInputResolver,
) -> JobListResolver:
    from merapy.codebase.app.task_queue_worker.model import Job

    page = max(1, f.page or 1)
    limit = max(1, min(100, f.limit or 20))
    offset = (page - 1) * limit

    async with session_factory() as session:
        stmt = select(Job)
        if f.task_name:
            stmt = stmt.where(Job.task_name == f.task_name)
        if f.statuses:
            stmt = stmt.where(Job.status.in_(f.statuses))
        if f.search:
            stmt = stmt.where(Job.arguments.ilike(f"%{f.search}%"))
        if f.job_id:
            stmt = stmt.where(Job.id == f.job_id)

        total = int(
            (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
        )
        rows = list(
            (await session.execute(stmt.order_by(Job.created_at.desc()).offset(offset).limit(limit))).scalars()
        )

    total_pages = max(1, (total + limit - 1) // limit)
    return JobListResolver(
        meta=MetaType(page=page, limit=limit, total_pages=total_pages, total_records=total),
        data=[
            JobResolver(
                id=r.id,
                task_name=r.task_name,
                arguments=r.arguments,
                retries=r.retries,
                max_retry=r.max_retry,
                interval=r.interval,
                status=r.status,
                error=r.error,
                result=r.result,
                trace_id=r.trace_id,
                created_at=_fmt(r.created_at),
                finished_at=_fmt(r.finished_at),
            )
            for r in rows
        ],
    )


# ---------------------------------------------------------------------------
# GraphQL schema — module-level state
# ---------------------------------------------------------------------------

_worker_ref: "TaskQueueWorker | None" = None  # set by _build_schema

# Asyncio condition — mutations notify this; subscriptions wait on it.
_change_condition: "asyncio.Condition | None" = None

# Active subscriber counter — incremented/decremented by listen_task_dashboard.
_active_subscribers: int = 0


def _get_condition() -> asyncio.Condition:
    global _change_condition
    if _change_condition is None:
        _change_condition = asyncio.Condition()
    return _change_condition


def _notify_change() -> None:
    """Signal all subscriptions that data has changed."""
    async def _do_notify() -> None:
        cond = _get_condition()
        async with cond:
            cond.notify_all()
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_do_notify())
    except RuntimeError:
        pass


async def _recalc_summary(session_factory: Any, task_name: str) -> None:
    """Recompute job_summaries for a task by counting directly from jobs table."""
    from merapy.codebase.app.task_queue_worker.model import Job, JobSummary, JobStatus
    async with session_factory() as session:  # type: ignore[misc]
        async with session.begin():
            counts: dict[str, int] = {}
            for status in [JobStatus.QUEUEING, JobStatus.RETRYING,
                           JobStatus.SUCCESS, JobStatus.FAILURE, JobStatus.STOPPED]:
                cnt = int(
                    (await session.execute(
                        select(func.count()).where(
                            Job.task_name == task_name,
                            Job.status == status,
                        )
                    )).scalar() or 0
                )
                counts[status] = cnt

            existing = await session.get(JobSummary, task_name)
            if existing is None:
                session.add(JobSummary(
                    id=task_name,
                    queueing=counts[JobStatus.QUEUEING],
                    retrying=counts[JobStatus.RETRYING],
                    success=counts[JobStatus.SUCCESS],
                    failure=counts[JobStatus.FAILURE],
                    stopped=counts[JobStatus.STOPPED],
                ))
            else:
                existing.queueing = counts[JobStatus.QUEUEING]
                existing.retrying = counts[JobStatus.RETRYING]
                existing.success = counts[JobStatus.SUCCESS]
                existing.failure = counts[JobStatus.FAILURE]
                existing.stopped = counts[JobStatus.STOPPED]


@strawberry.type
class TaskDetailResolver:
    failure: int = 0
    retrying: int = 0
    success: int = 0
    queueing: int = 0
    stopped: int = 0


@strawberry.type
class TaskResolver:
    name: str
    module_name: str
    total_jobs: int
    is_loading: bool = False
    detail: TaskDetailResolver = strawberry.field(default_factory=TaskDetailResolver)


@strawberry.type
class MetaTaskResolver:
    page: int
    limit: int
    total_pages: int
    total_records: int
    is_close_session: bool = False
    total_client_subscriber: int = 0
    client_id: str = ""


@strawberry.type
class TaskListResolver:
    meta: MetaTaskResolver
    data: list[TaskResolver]
    stats: WorkerStatsResolver = strawberry.field(default_factory=WorkerStatsResolver)


async def _get_all_task_impl() -> list[TaskResolver]:
    """Fetch task summaries for all registered handlers."""
    from merapy.codebase.app.task_queue_worker.model import JobSummary
    w = _worker_ref
    if w is None or not w._handlers:
        return []
    tasks: list[TaskResolver] = []
    if w._session_factory is None:
        for name in w._handlers.keys():
            tasks.append(TaskResolver(name=name, module_name=name, total_jobs=0,
                                      detail=TaskDetailResolver()))
        return tasks
    async with w._session_factory() as session:  # type: ignore[misc]
        rows = list((await session.execute(select(JobSummary))).scalars())
    summary_map = {r.id: r for r in rows}
    for name in w._handlers.keys():
        s = summary_map.get(name)
        detail = TaskDetailResolver(
            failure=s.failure if s else 0,
            retrying=s.retrying if s else 0,
            success=s.success if s else 0,
            queueing=s.queueing if s else 0,
            stopped=s.stopped if s else 0,
        )
        total = detail.failure + detail.retrying + detail.success + detail.queueing + detail.stopped
        tasks.append(TaskResolver(name=name, module_name=name, total_jobs=total, detail=detail))
    return tasks


@strawberry.type
class _Query:
    @strawberry.field
    async def get_all_job(self, filter: Optional[GetAllJobInputResolver] = None) -> JobListResolver:
        w = _worker_ref
        if w is None:
            return JobListResolver(meta=MetaType(page=1, limit=20, total_pages=0, total_records=0), data=[])
        return await _query_jobs(w._session_factory, filter or GetAllJobInputResolver())

    @strawberry.field
    async def get_count_job(self, filter: Optional[GetAllJobInputResolver] = None) -> int:
        w = _worker_ref
        if w is None:
            return 0
        result = await _query_jobs(w._session_factory, filter or GetAllJobInputResolver())
        return result.meta.total_records

    @strawberry.field
    async def get_all_task(self) -> list[TaskResolver]:
        return await _get_all_task_impl()

    @strawberry.field
    def get_worker_stats(self) -> WorkerStatsResolver:
        return _get_worker_stats()


@strawberry.type
class _Mutation:
    @strawberry.mutation
    async def add_job(self, param: AddJobInputResolver) -> str:
        from merapy.codebase.app.task_queue_worker.model import Job, JobStatus
        w = _worker_ref
        assert w is not None and w._session_factory is not None
        async with w._session_factory() as session:  # type: ignore[misc]
            async with session.begin():
                job = Job(
                    task_name=param.task_name,
                    arguments=param.args,
                    max_retry=param.max_retry,
                    status=JobStatus.QUEUEING,
                    created_at=datetime.now(tz=timezone.utc),
                    updated_at=datetime.now(tz=timezone.utc),
                )
                session.add(job)
                await session.flush()
                job_id = job.id
        await _recalc_summary(w._session_factory, param.task_name)
        _notify_change()
        return job_id

    @strawberry.mutation
    async def retry_job(self, job_id: str) -> str:
        from merapy.codebase.app.task_queue_worker.model import Job, JobStatus
        w = _worker_ref
        assert w is not None and w._session_factory is not None
        task_name: str = ""
        async with w._session_factory() as session:  # type: ignore[misc]
            async with session.begin():
                job = await session.get(Job, job_id)
                if job:
                    task_name = job.task_name
                await session.execute(
                    update(Job).where(Job.id == job_id).values(
                        status=JobStatus.QUEUEING, retries=0, error="",
                        finished_at=None, updated_at=datetime.now(tz=timezone.utc),
                    )
                )
        if task_name:
            await _recalc_summary(w._session_factory, task_name)
        _notify_change()
        return "ok"

    @strawberry.mutation
    async def stop_job(self, job_id: str) -> str:
        from merapy.codebase.app.task_queue_worker.model import Job, JobStatus
        w = _worker_ref
        assert w is not None and w._session_factory is not None
        task_name: str = ""
        async with w._session_factory() as session:  # type: ignore[misc]
            async with session.begin():
                job = await session.get(Job, job_id)
                if job:
                    task_name = job.task_name
                await session.execute(
                    update(Job).where(Job.id == job_id).values(
                        status=JobStatus.STOPPED,
                        updated_at=datetime.now(tz=timezone.utc),
                    )
                )
        if task_name:
            await _recalc_summary(w._session_factory, task_name)
        _notify_change()
        return "ok"

    @strawberry.mutation
    async def stop_all_job(self, task_name: str) -> str:
        from merapy.codebase.app.task_queue_worker.model import Job, JobStatus
        w = _worker_ref
        assert w is not None and w._session_factory is not None
        async with w._session_factory() as session:  # type: ignore[misc]
            async with session.begin():
                await session.execute(
                    update(Job)
                    .where(
                        Job.task_name == task_name,
                        Job.status.in_([JobStatus.QUEUEING, JobStatus.RETRYING]),
                    )
                    .values(status=JobStatus.STOPPED, updated_at=datetime.now(tz=timezone.utc))
                )
        await _recalc_summary(w._session_factory, task_name)
        _notify_change()
        return "ok"

    @strawberry.mutation
    async def retry_all_job(self, filter: FilterMutateJobInputResolver) -> str:
        """Re-queue jobs for a task. If ``filter.statuses`` is empty, retries ALL jobs."""
        from merapy.codebase.app.task_queue_worker.model import Job, JobStatus
        w = _worker_ref
        assert w is not None and w._session_factory is not None
        async with w._session_factory() as session:  # type: ignore[misc]
            async with session.begin():
                stmt = update(Job).where(Job.task_name == filter.task_name).values(
                    status=JobStatus.QUEUEING, retries=0, error="",
                    finished_at=None, updated_at=datetime.now(tz=timezone.utc),
                )
                if filter.statuses:
                    stmt = stmt.where(Job.status.in_(filter.statuses))
                await session.execute(stmt)
        await _recalc_summary(w._session_factory, filter.task_name)
        _notify_change()
        return "ok"

    @strawberry.mutation
    async def delete_job(self, job_id: str) -> str:
        from merapy.codebase.app.task_queue_worker.model import Job
        w = _worker_ref
        assert w is not None and w._session_factory is not None
        task_name: str = ""
        async with w._session_factory() as session:  # type: ignore[misc]
            async with session.begin():
                job = await session.get(Job, job_id)
                if job:
                    task_name = job.task_name
                await session.execute(delete(Job).where(Job.id == job_id))
        if task_name:
            await _recalc_summary(w._session_factory, task_name)
        _notify_change()
        return "ok"

    @strawberry.mutation
    async def clean_job(self, filter: FilterMutateJobInputResolver) -> str:
        from merapy.codebase.app.task_queue_worker.model import Job
        w = _worker_ref
        assert w is not None and w._session_factory is not None
        async with w._session_factory() as session:  # type: ignore[misc]
            async with session.begin():
                stmt = delete(Job).where(Job.task_name == filter.task_name)
                if filter.statuses:
                    stmt = stmt.where(Job.status.in_(filter.statuses))
                await session.execute(stmt)
        await _recalc_summary(w._session_factory, filter.task_name)
        _notify_change()
        return "ok"


@strawberry.type
class _Subscription:
    @strawberry.subscription
    async def listen_task_dashboard(
        self,
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
    ) -> AsyncGenerator[TaskListResolver, None]:
        """Push task summary + worker stats on change OR every 2 seconds."""
        global _active_subscribers
        _active_subscribers += 1
        _notify_change()

        async def _fetch() -> TaskListResolver:
            tasks = await _get_all_task_impl()
            if search:
                tasks = [t for t in tasks if search.lower() in t.name.lower()]
            total = len(tasks)
            offset = (page - 1) * limit
            return TaskListResolver(
                meta=MetaTaskResolver(
                    page=page, limit=limit,
                    total_pages=max(1, (total + limit - 1) // limit),
                    total_records=total,
                    total_client_subscriber=_active_subscribers,
                ),
                data=tasks[offset: offset + limit],
                stats=_get_worker_stats(),
            )

        try:
            yield await _fetch()
            while True:
                cond = _get_condition()
                async with cond:
                    try:
                        await asyncio.wait_for(cond.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        pass
                yield await _fetch()
        finally:
            _active_subscribers -= 1
            _notify_change()

    @strawberry.subscription
    async def listen_all_job(
        self,
        filter: Optional[GetAllJobInputResolver] = None,
    ) -> AsyncGenerator[JobListResolver, None]:
        """Push job list on change OR every 2 seconds."""
        async def _fetch() -> JobListResolver:
            w = _worker_ref
            if w is None or w._session_factory is None:
                return JobListResolver(
                    meta=MetaType(page=1, limit=20, total_pages=0, total_records=0),
                    data=[],
                )
            return await _query_jobs(w._session_factory, filter or GetAllJobInputResolver())

        yield await _fetch()
        while True:
            cond = _get_condition()
            async with cond:
                try:
                    await asyncio.wait_for(cond.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass
            yield await _fetch()


def _build_schema(worker: "TaskQueueWorker") -> strawberry.Schema:
    global _worker_ref
    _worker_ref = worker
    from strawberry.schema.config import StrawberryConfig
    return strawberry.Schema(
        query=_Query,
        mutation=_Mutation,
        subscription=_Subscription,
        config=StrawberryConfig(auto_camel_case=False),
    )

# ---------------------------------------------------------------------------
# Static file discovery
# ---------------------------------------------------------------------------

def _find_static_dir() -> Path | None:
    """Find the built Next.js dashboard static files."""
    pkg_dir = Path(__file__).parent / "dashboard_static"
    if pkg_dir.is_dir() and (pkg_dir / "index.html").exists():
        return pkg_dir

    env_dir = os.environ.get("MERAPY_DASHBOARD_DIR")
    if env_dir and Path(env_dir).is_dir():
        return Path(env_dir)

    cwd_dir = Path.cwd() / "dashboard"
    if cwd_dir.is_dir() and (cwd_dir / "index.html").exists():
        return cwd_dir

    return None


# ---------------------------------------------------------------------------
# Dashboard server
# ---------------------------------------------------------------------------

class TaskQueueDashboard:
    """Serves the GraphQL API + static dashboard UI on TASK_QUEUE_DASHBOARD_PORT."""

    name = "task-queue-dashboard"

    def __init__(self, worker: "TaskQueueWorker", port: int = 8080) -> None:
        self._worker = worker
        self._port = port
        self._server: uvicorn.Server | None = None

    def build_app(self) -> FastAPI:
        schema = _build_schema(self._worker)
        app = FastAPI(title="Merapy Task Queue Dashboard", docs_url=None, redoc_url=None)

        graphql_router: GraphQLRouter[Any, Any] = GraphQLRouter(
            schema,
            subscription_protocols=["graphql-transport-ws", "graphql-ws"],
        )
        app.include_router(graphql_router, prefix="/graphql")

        static_dir = _find_static_dir()
        if static_dir:
            next_static = static_dir / "_next"
            if next_static.is_dir():
                app.mount("/_next", StaticFiles(directory=str(next_static)), name="next-static")

            @app.get("/", include_in_schema=False, response_model=None)
            @app.get("/{path:path}", include_in_schema=False, response_model=None)
            async def serve_spa(path: str = "") -> FileResponse | HTMLResponse:
                clean = path.rstrip("/")
                if clean:
                    candidate = static_dir / clean
                    if candidate.is_file():
                        return FileResponse(str(candidate))
                if clean:
                    index_candidate = static_dir / clean / "index.html"
                    if index_candidate.is_file():
                        return FileResponse(str(index_candidate))
                if clean:
                    html_candidate = static_dir / f"{clean}.html"
                    if html_candidate.is_file():
                        return FileResponse(str(html_candidate))
                root_index = static_dir / "index.html"
                if root_index.is_file():
                    return FileResponse(str(root_index))
                return HTMLResponse("<h1>Dashboard not found</h1>", status_code=404)
        else:
            @app.get("/", include_in_schema=False, response_model=None)
            async def health() -> dict[str, str]:
                return {
                    "status": "ok",
                    "graphql": f"http://localhost:{self._port}/graphql",
                    "dashboard": (
                        "Build merapy-taskqueue-dashboard and copy out/ to <service>/dashboard/ "
                        "or set MERAPY_DASHBOARD_DIR env var"
                    ),
                }

        return app

    async def serve(self) -> None:
        app = self.build_app()
        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=self._port,
            log_config=None,
            access_log=False,
            lifespan="on",
            ws="websockets",
        )
        self._server = uvicorn.Server(config)
        await self._server.serve()

    async def shutdown(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
            await asyncio.sleep(0)
