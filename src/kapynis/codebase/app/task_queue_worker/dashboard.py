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

def _build_schema(worker: "TaskQueueWorker") -> strawberry.Schema:

    @strawberry.type
    class Query:
        @strawberry.field
        async def get_all_job(
            self, filter: Optional[GetAllJobInputResolver] = None
        ) -> JobListResolver:
            return await _query_jobs(worker._session_factory, filter or GetAllJobInputResolver())

        @strawberry.field
        async def get_count_job(
            self, filter: Optional[GetAllJobInputResolver] = None
        ) -> int:
            result = await _query_jobs(worker._session_factory, filter or GetAllJobInputResolver())
            return result.meta.total_records

    @strawberry.type
    class Mutation:
        @strawberry.mutation
        async def add_job(self, param: AddJobInputResolver) -> str:
            from kapynis.codebase.app.task_queue_worker.model import Job, JobStatus
            async with worker._session_factory() as session:  # type: ignore[misc]
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
            async with worker._session_factory() as session:  # type: ignore[misc]
                async with session.begin():
                    await session.execute(
                        update(Job).where(Job.id == job_id).values(
                            status=JobStatus.QUEUEING,
                            retries=0,
                            error="",
                            finished_at=None,
                            updated_at=datetime.now(tz=timezone.utc),
                        )
                    )
            return "ok"

        @strawberry.mutation
        async def retry_all_job(self, filter: FilterMutateJobInputResolver) -> str:
            from kapynis.codebase.app.task_queue_worker.model import Job, JobStatus
            async with worker._session_factory() as session:  # type: ignore[misc]
                async with session.begin():
                    stmt = update(Job).where(Job.task_name == filter.task_name).values(
                        status=JobStatus.QUEUEING,
                        retries=0,
                        error="",
                        finished_at=None,
                        updated_at=datetime.now(tz=timezone.utc),
                    )
                    if filter.statuses:
                        stmt = stmt.where(Job.status.in_(filter.statuses))
                    await session.execute(stmt)
            return "ok"

        @strawberry.mutation
        async def delete_job(self, job_id: str) -> str:
            from kapynis.codebase.app.task_queue_worker.model import Job
            async with worker._session_factory() as session:  # type: ignore[misc]
                async with session.begin():
                    await session.execute(delete(Job).where(Job.id == job_id))
            return "ok"

        @strawberry.mutation
        async def clean_job(self, filter: FilterMutateJobInputResolver) -> str:
            from kapynis.codebase.app.task_queue_worker.model import Job
            async with worker._session_factory() as session:  # type: ignore[misc]
                async with session.begin():
                    stmt = delete(Job).where(Job.task_name == filter.task_name)
                    if filter.statuses:
                        stmt = stmt.where(Job.status.in_(filter.statuses))
                    await session.execute(stmt)
            return "ok"

    return strawberry.Schema(query=Query, mutation=Mutation)


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

        # GraphQL endpoint
        graphql_router: GraphQLRouter[Any, Any] = GraphQLRouter(schema)
        app.include_router(graphql_router, prefix="/graphql")

        # Static dashboard UI
        static_dir = _find_static_dir()
        if static_dir:
            # Serve _next/ assets
            next_static = static_dir / "_next"
            if next_static.is_dir():
                app.mount("/_next", StaticFiles(directory=str(next_static)), name="next-static")

            @app.get("/", include_in_schema=False)
            @app.get("/{path:path}", include_in_schema=False)
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
            @app.get("/", include_in_schema=False)
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
            lifespan="off",
        )
        self._server = uvicorn.Server(config)
        await self._server.serve()

    async def shutdown(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
            await asyncio.sleep(0)
