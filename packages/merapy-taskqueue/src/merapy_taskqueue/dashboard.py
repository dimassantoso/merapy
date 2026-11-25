"""Standalone Task Queue Dashboard server (FastAPI + Strawberry GraphQL + static SPA)."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import strawberry
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from strawberry.fastapi import GraphQLRouter
from strawberry.schema.config import StrawberryConfig

from merapy_taskqueue.types import DashboardConfig, JobFilter, JobRecord

if TYPE_CHECKING:
    from merapy_taskqueue.worker import TaskQueue


# ---------------------------------------------------------------------------
# GraphQL types (snake_case via StrawberryConfig(auto_camel_case=False))
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
    page: int | None = 1
    limit: int | None = 20
    task_name: str | None = None
    search: str | None = None
    statuses: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None
    job_id: str | None = None


@strawberry.input
class AddJobInputResolver:
    task_name: str
    max_retry: int
    args: str
    retry_interval: str | None = None


@strawberry.input
class FilterMutateJobInputResolver:
    task_name: str
    search: str | None = None
    job_id: str | None = None
    statuses: list[str] = strawberry.field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None


@strawberry.type
class WorkerStatsResolver:
    """Process memory, CPU, and build metadata snapshot."""

    memory_rss_mb: float = 0.0
    memory_vms_mb: float = 0.0
    memory_percent: float = 0.0
    cpu_percent: float = 0.0
    merapy_version: str = ""
    service_name: str = ""
    service_version: str = ""
    build_number: str = ""
    git_commit: str = ""
    build_date: str = ""


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt_dt(dt: datetime | None) -> str:
    return dt.isoformat() if dt else ""


def _record_to_resolver(rec: JobRecord) -> JobResolver:
    return JobResolver(
        id=rec.id,
        task_name=rec.task_name,
        arguments=rec.arguments,
        retries=rec.retries,
        max_retry=rec.max_retry,
        interval=rec.interval,
        status=rec.status,
        error=rec.error,
        result=rec.result,
        trace_id=rec.trace_id,
        created_at=_fmt_dt(rec.created_at),
        finished_at=_fmt_dt(rec.finished_at),
    )


def _to_job_filter(f: GetAllJobInputResolver | None) -> JobFilter:
    if f is None:
        return JobFilter()
    search = f.search[:256] if f.search else None
    return JobFilter(
        page=max(1, f.page or 1),
        limit=max(1, min(100, f.limit or 20)),
        task_name=f.task_name,
        search=search,
        statuses=f.statuses,
        start_date=f.start_date,
        end_date=f.end_date,
        job_id=f.job_id,
    )


def collect_worker_stats(cfg: DashboardConfig) -> WorkerStatsResolver:
    """Collect process memory/CPU metrics using psutil or stdlib resource."""
    from merapy_taskqueue import __version__ as tq_version  # noqa: PLC0415

    fw_version = cfg.framework_version or tq_version
    service_name = cfg.service_name or os.environ.get("SERVICE_NAME", "")
    service_version = cfg.service_version or os.environ.get("APP_VERSION", "")
    build_number = cfg.build_number or os.environ.get("BUILD_NUMBER", "")
    git_commit = cfg.git_commit or os.environ.get("GIT_COMMIT", "")
    build_date = cfg.build_date or os.environ.get("BUILD_DATE", "")

    try:
        import psutil  # type: ignore[import-untyped]  # noqa: PLC0415

        proc = psutil.Process(os.getpid())
        mem = proc.memory_info()
        return WorkerStatsResolver(
            memory_rss_mb=round(mem.rss / 1024 / 1024, 2),
            memory_vms_mb=round(mem.vms / 1024 / 1024, 2),
            memory_percent=round(proc.memory_percent(), 2),
            cpu_percent=round(proc.cpu_percent(interval=None), 2),
            merapy_version=fw_version,
            service_name=service_name,
            service_version=service_version,
            build_number=build_number,
            git_commit=git_commit,
            build_date=build_date,
        )
    except ImportError:
        pass

    try:
        import resource  # noqa: PLC0415

        usage = resource.getrusage(resource.RUSAGE_SELF)
        rss_bytes = usage.ru_maxrss * (1 if sys.platform == "linux" else 1024)
        return WorkerStatsResolver(
            memory_rss_mb=round(rss_bytes / 1024 / 1024, 2),
            merapy_version=fw_version,
            service_name=service_name,
            service_version=service_version,
            build_number=build_number,
            git_commit=git_commit,
            build_date=build_date,
        )
    except Exception:
        pass

    return WorkerStatsResolver(
        merapy_version=fw_version,
        service_name=service_name,
        service_version=service_version,
        build_number=build_number,
        git_commit=git_commit,
        build_date=build_date,
    )


def find_static_dir(explicit: str | None = None) -> Path | None:
    """Locate built dashboard static files."""
    if explicit:
        p = Path(explicit)
        if p.is_dir() and (p / "index.html").is_file():
            return p.resolve()

    env_dir = os.environ.get("MERAPY_DASHBOARD_DIR")
    if env_dir:
        p = Path(env_dir)
        if p.is_dir() and (p / "index.html").is_file():
            return p.resolve()

    pkg_dir = Path(__file__).parent / "dashboard_static"
    if pkg_dir.is_dir() and (pkg_dir / "index.html").is_file():
        return pkg_dir.resolve()

    cwd_dir = Path.cwd() / "dashboard"
    if cwd_dir.is_dir() and (cwd_dir / "index.html").is_file():
        return cwd_dir.resolve()

    return None


def _safe_static_file(static_root: Path, rel_path: str) -> Path | None:
    """Resolve ``rel_path`` under ``static_root`` while blocking path traversal."""
    if not rel_path or "\x00" in rel_path:
        return None
    candidate = (static_root / rel_path).resolve()
    if not candidate.is_relative_to(static_root):
        return None
    return candidate if candidate.is_file() else None


def build_schema(queue: TaskQueue, config: DashboardConfig) -> strawberry.Schema:
    """Create a per-instance Strawberry GraphQL schema bound to ``queue``."""
    active_subscribers = {"count": 0}

    async def _all_tasks() -> list[TaskResolver]:
        summaries = await queue.get_task_summaries()
        return [
            TaskResolver(
                name=s.name,
                module_name=s.module_name,
                total_jobs=s.counts.total,
                is_loading=s.is_loading,
                detail=TaskDetailResolver(
                    queueing=s.counts.queueing,
                    retrying=s.counts.retrying,
                    success=s.counts.success,
                    failure=s.counts.failure,
                    stopped=s.counts.stopped,
                ),
            )
            for s in summaries
        ]

    @strawberry.type
    class Query:
        @strawberry.field
        async def get_all_job(self, filter: GetAllJobInputResolver | None = None) -> JobListResolver:
            page = await queue.store.list_jobs(_to_job_filter(filter))
            return JobListResolver(
                meta=MetaType(
                    page=page.page,
                    limit=page.limit,
                    total_pages=page.total_pages,
                    total_records=page.total_records,
                ),
                data=[_record_to_resolver(r) for r in page.items],
            )

        @strawberry.field
        async def get_count_job(self, filter: GetAllJobInputResolver | None = None) -> int:
            return await queue.store.count_jobs(_to_job_filter(filter))

        @strawberry.field
        async def get_all_task(self) -> list[TaskResolver]:
            return await _all_tasks()

        @strawberry.field
        def get_worker_stats(self) -> WorkerStatsResolver:
            return collect_worker_stats(config)

    @strawberry.type
    class Mutation:
        @strawberry.mutation
        async def add_job(self, param: AddJobInputResolver) -> str:
            return await queue.enqueue(
                param.task_name,
                param.args,
                max_retry=param.max_retry,
                interval=param.retry_interval or "",
            )

        @strawberry.mutation
        async def retry_job(self, job_id: str) -> str:
            await queue.store.retry_job(job_id)
            queue.notify_change()
            return "ok"

        @strawberry.mutation
        async def stop_job(self, job_id: str) -> str:
            await queue.store.stop_job(job_id)
            queue.notify_change()
            return "ok"

        @strawberry.mutation
        async def stop_all_job(self, task_name: str) -> str:
            await queue.store.stop_all(task_name)
            queue.notify_change()
            return "ok"

        @strawberry.mutation
        async def retry_all_job(self, filter: FilterMutateJobInputResolver) -> str:
            await queue.store.retry_all(
                filter.task_name,
                statuses=filter.statuses or None,
                search=filter.search,
            )
            queue.notify_change()
            return "ok"

        @strawberry.mutation
        async def delete_job(self, job_id: str) -> str:
            await queue.store.delete_job(job_id)
            queue.notify_change()
            return "ok"

        @strawberry.mutation
        async def clean_job(self, filter: FilterMutateJobInputResolver) -> str:
            await queue.store.clean_jobs(
                filter.task_name,
                statuses=filter.statuses or None,
                search=filter.search,
            )
            queue.notify_change()
            return "ok"

    @strawberry.type
    class Subscription:
        @strawberry.subscription
        async def listen_task_dashboard(
            self,
            page: int = 1,
            limit: int = 10,
            search: str | None = None,
        ) -> AsyncGenerator[TaskListResolver, None]:
            active_subscribers["count"] += 1
            queue.notify_change()
            safe_page = max(1, page)
            safe_limit = max(1, min(100, limit))

            async def _fetch() -> TaskListResolver:
                tasks = await _all_tasks()
                if search:
                    needle = search.lower()
                    tasks = [t for t in tasks if needle in t.name.lower()]
                total = len(tasks)
                offset = (safe_page - 1) * safe_limit
                return TaskListResolver(
                    meta=MetaTaskResolver(
                        page=safe_page,
                        limit=safe_limit,
                        total_pages=max(1, (total + safe_limit - 1) // safe_limit),
                        total_records=total,
                        total_client_subscriber=active_subscribers["count"],
                    ),
                    data=tasks[offset : offset + safe_limit],
                    stats=collect_worker_stats(config),
                )

            try:
                yield await _fetch()
                while True:
                    await queue.wait_for_change(timeout=2.0)
                    yield await _fetch()
            finally:
                active_subscribers["count"] = max(0, active_subscribers["count"] - 1)
                queue.notify_change()

        @strawberry.subscription
        async def listen_all_job(
            self,
            filter: GetAllJobInputResolver | None = None,
        ) -> AsyncGenerator[JobListResolver, None]:
            flt = _to_job_filter(filter)

            async def _fetch() -> JobListResolver:
                page = await queue.store.list_jobs(flt)
                return JobListResolver(
                    meta=MetaType(
                        page=page.page,
                        limit=page.limit,
                        total_pages=page.total_pages,
                        total_records=page.total_records,
                    ),
                    data=[_record_to_resolver(r) for r in page.items],
                )

            yield await _fetch()
            while True:
                await queue.wait_for_change(timeout=2.0)
                yield await _fetch()

    return strawberry.Schema(
        query=Query,
        mutation=Mutation,
        subscription=Subscription,
        config=StrawberryConfig(auto_camel_case=False),
    )


class TaskQueueDashboard:
    """Serves the GraphQL API + embedded Vite/Preact SPA dashboard."""

    name = "task-queue-dashboard"

    def __init__(
        self,
        queue: TaskQueue,
        config: DashboardConfig | None = None,
        *,
        port: int | None = None,
    ) -> None:
        self._queue = queue
        self._config = config or queue.dashboard_config
        if port is not None:
            self._config.port = port
        self._server: uvicorn.Server | None = None

    def build_app(self) -> FastAPI:
        schema = build_schema(self._queue, self._config)
        app = FastAPI(title="Merapy Task Queue Dashboard", docs_url=None, redoc_url=None)

        graphql_router: GraphQLRouter[Any, Any] = GraphQLRouter(
            schema,
            subscription_protocols=["graphql-transport-ws", "graphql-ws"],
        )
        app.include_router(graphql_router, prefix="/graphql")

        static_root = find_static_dir(self._config.static_dir)
        if static_root is not None:
            assets_dir = static_root / "assets"
            if assets_dir.is_dir():
                app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
            next_static = static_root / "_next"
            if next_static.is_dir():
                app.mount("/_next", StaticFiles(directory=str(next_static)), name="next-static")

            @app.get("/", include_in_schema=False, response_model=None)
            @app.get("/{path:path}", include_in_schema=False, response_model=None)
            async def serve_spa(path: str = "") -> FileResponse | HTMLResponse:
                clean = path.strip("/")
                if clean:
                    for rel in (clean, f"{clean}/index.html", f"{clean}.html"):
                        found = _safe_static_file(static_root, rel)
                        if found is not None:
                            return FileResponse(str(found))
                root_index = static_root / "index.html"
                if root_index.is_file():
                    return FileResponse(str(root_index))
                return HTMLResponse("<h1>Dashboard not found</h1>", status_code=404)
        else:

            @app.get("/", include_in_schema=False, response_model=None)
            async def health() -> dict[str, str]:
                return {
                    "status": "ok",
                    "graphql": f"http://localhost:{self._config.port}/graphql",
                    "dashboard": "Set MERAPY_DASHBOARD_DIR or build packages/merapy-taskqueue/ui",
                }

        return app

    async def serve(self) -> None:
        app = self.build_app()
        uv_cfg = uvicorn.Config(
            app,
            host=self._config.host,
            port=self._config.port,
            log_config=None,
            access_log=False,
            lifespan="on",
            ws="websockets",
        )
        self._server = uvicorn.Server(uv_cfg)
        await self._server.serve()

    async def shutdown(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
            await asyncio.sleep(0)
