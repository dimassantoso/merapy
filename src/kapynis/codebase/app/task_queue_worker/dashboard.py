"""Task Queue Worker Dashboard server.

Serves two things on ``TASK_QUEUE_DASHBOARD_PORT`` (default 8080):

1. ``/graphql``  — GraphQL API the dashboard JS calls (queries + mutations)
2. ``/``         — Static Next.js dashboard UI (built from kapynis-taskqueue-dashboard)

The static files are looked up in this order:
  a. ``KAPYNIS_DASHBOARD_DIR`` env var (absolute path)
  b. ``<service_root>/dashboard/`` — user can copy the built ``out/`` folder here
  c. Bundled fallback inside kapynis package (if shipped)

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
    from kapynis.codebase.app.task_queue_worker.worker import TaskQueueWorker


# ---------------------------------------------------------------------------
# GraphQL types — mirrors candi's graphql_schema.go field names exactly
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
# Helpers
# ---------------------------------------------------------------------------

def _fmt(dt: datetime | None) -> str:
    return dt.isoformat() if dt else ""


async def _query_jobs(
    session_factory: Any,
    f: GetAllJobInputResolver,
) -> JobListResolver:
    from kapynis.codebase.app.task_queue_worker.model import Job

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
            stmt = stmt.where(Job.task_name.ilike(f"%{f.search}%"))
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
# GraphQL schema
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# GraphQL schema — module-level worker reference so strawberry can resolve types
# ---------------------------------------------------------------------------

_worker_ref: "TaskQueueWorker | None" = None  # set by _build_schema


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


async def _get_all_task_impl() -> list[TaskResolver]:
    """Fetch task summaries for all registered handlers."""
    from kapynis.codebase.app.task_queue_worker.model import JobSummary
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


@strawberry.type
class _Mutation:
    @strawberry.mutation
    async def add_job(self, param: AddJobInputResolver) -> str:
        from kapynis.codebase.app.task_queue_worker.model import Job, JobStatus
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
                return job.id

    @strawberry.mutation
    async def retry_job(self, job_id: str) -> str:
        from kapynis.codebase.app.task_queue_worker.model import Job, JobStatus
        w = _worker_ref
        assert w is not None and w._session_factory is not None
        async with w._session_factory() as session:  # type: ignore[misc]
            async with session.begin():
                await session.execute(
                    update(Job).where(Job.id == job_id).values(
                        status=JobStatus.QUEUEING, retries=0, error="",
                        finished_at=None, updated_at=datetime.now(tz=timezone.utc),
                    )
                )
        return "ok"

    @strawberry.mutation
    async def stop_job(self, job_id: str) -> str:
        """Stop a single running/queued job — sets status to STOPPED."""
        from kapynis.codebase.app.task_queue_worker.model import Job, JobStatus
        w = _worker_ref
        assert w is not None and w._session_factory is not None
        async with w._session_factory() as session:  # type: ignore[misc]
            async with session.begin():
                await session.execute(
                    update(Job).where(Job.id == job_id).values(
                        status=JobStatus.STOPPED,
                        updated_at=datetime.now(tz=timezone.utc),
                    )
                )
        return "ok"

    @strawberry.mutation
    async def stop_all_job(self, task_name: str) -> str:
        """Stop all QUEUEING and RETRYING jobs for a task — sets them to STOPPED."""
        from kapynis.codebase.app.task_queue_worker.model import Job, JobStatus
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
        return "ok"

    @strawberry.mutation
    async def retry_all_job(self, filter: FilterMutateJobInputResolver) -> str:
        from kapynis.codebase.app.task_queue_worker.model import Job, JobStatus
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
        return "ok"

    @strawberry.mutation
    async def delete_job(self, job_id: str) -> str:
        from kapynis.codebase.app.task_queue_worker.model import Job
        w = _worker_ref
        assert w is not None and w._session_factory is not None
        async with w._session_factory() as session:  # type: ignore[misc]
            async with session.begin():
                await session.execute(delete(Job).where(Job.id == job_id))
        return "ok"

    @strawberry.mutation
    async def clean_job(self, filter: FilterMutateJobInputResolver) -> str:
        from kapynis.codebase.app.task_queue_worker.model import Job
        w = _worker_ref
        assert w is not None and w._session_factory is not None
        async with w._session_factory() as session:  # type: ignore[misc]
            async with session.begin():
                stmt = delete(Job).where(Job.task_name == filter.task_name)
                if filter.statuses:
                    stmt = stmt.where(Job.status.in_(filter.statuses))
                await session.execute(stmt)
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
        """Push task summary every 2 seconds — mirrors candi's listen_task_dashboard."""
        while True:
            tasks = await _get_all_task_impl()
            # Apply search filter
            if search:
                tasks = [t for t in tasks if search.lower() in t.name.lower()]
            total = len(tasks)
            offset = (page - 1) * limit
            paged = tasks[offset: offset + limit]
            yield TaskListResolver(
                meta=MetaTaskResolver(
                    page=page,
                    limit=limit,
                    total_pages=max(1, (total + limit - 1) // limit),
                    total_records=total,
                ),
                data=paged,
            )
            await asyncio.sleep(2)

    @strawberry.subscription
    async def listen_all_job(
        self,
        filter: Optional[GetAllJobInputResolver] = None,
    ) -> AsyncGenerator[JobListResolver, None]:
        """Push job list every 2 seconds — mirrors candi's listen_all_job."""
        while True:
            w = _worker_ref
            if w is None or w._session_factory is None:
                yield JobListResolver(
                    meta=MetaType(page=1, limit=20, total_pages=0, total_records=0),
                    data=[],
                )
            else:
                result = await _query_jobs(w._session_factory, filter or GetAllJobInputResolver())
                yield result
            await asyncio.sleep(2)


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
    """Find the built Next.js dashboard static files.

    Lookup order (mirrors candi's embed.FS approach):
    1. Bundled inside kapynis package at dashboard_static/ — populated by
       running `make embed` in kapynis-taskqueue-dashboard
    2. KAPYNIS_DASHBOARD_DIR env var (absolute path override)
    3. <cwd>/dashboard/ — user manually copies kapynis-taskqueue-dashboard/out/ here
    """
    # 1. Bundled inside kapynis package (preferred — zero config for users)
    pkg_dir = Path(__file__).parent / "dashboard_static"
    if pkg_dir.is_dir() and (pkg_dir / "index.html").exists():
        return pkg_dir

    # 2. Explicit env override
    env_dir = os.environ.get("KAPYNIS_DASHBOARD_DIR")
    if env_dir and Path(env_dir).is_dir():
        return Path(env_dir)

    # 3. <cwd>/dashboard/ — user copies out/ here
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
        app = FastAPI(title="Kapynis Task Queue Dashboard", docs_url=None, redoc_url=None)

        # GraphQL endpoint — with WebSocket subscription support
        graphql_router: GraphQLRouter[Any, Any] = GraphQLRouter(
            schema,
            subscription_protocols=["graphql-transport-ws", "graphql-ws"],
        )
        app.include_router(graphql_router, prefix="/graphql")

        # Static dashboard UI
        static_dir = _find_static_dir()
        if static_dir:
            # Serve _next/ assets
            next_static = static_dir / "_next"
            if next_static.is_dir():
                app.mount("/_next", StaticFiles(directory=str(next_static)), name="next-static")

            @app.get("/", include_in_schema=False, response_model=None)
            @app.get("/{path:path}", include_in_schema=False, response_model=None)
            async def serve_spa(path: str = "") -> FileResponse | HTMLResponse:
                # Try exact file first
                candidate = static_dir / path
                if candidate.is_file():
                    return FileResponse(str(candidate))
                # Try with .html
                html_candidate = static_dir / f"{path}.html"
                if html_candidate.is_file():
                    return FileResponse(str(html_candidate))
                # Fall back to index.html (SPA routing)
                index = static_dir / "index.html"
                if index.is_file():
                    return FileResponse(str(index))
                return HTMLResponse("<h1>Dashboard not found</h1>", status_code=404)
        else:
            @app.get("/", include_in_schema=False, response_model=None)
            async def health() -> dict[str, str]:
                return {
                    "status": "ok",
                    "graphql": f"http://localhost:{self._port}/graphql",
                    "dashboard": (
                        "Build kapynis-taskqueue-dashboard and copy out/ to <service>/dashboard/ "
                        "or set KAPYNIS_DASHBOARD_DIR env var"
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
            lifespan="on",   # subscriptions need lifespan ON for strawberry ws
            ws="websockets",
        )
        self._server = uvicorn.Server(config)
        await self._server.serve()

    async def shutdown(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
            await asyncio.sleep(0)
