"""SQLAlchemy 2.x async ``JobStore`` and canonical 4-table candi-compatible ORM schema."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, delete, func, select, update
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from merapy_taskqueue.store.base import JobStore
from merapy_taskqueue.types import (
    ALL_JOB_STATUSES,
    JobFilter,
    JobPage,
    JobRecord,
    JobStatus,
    TaskCounts,
    new_job_id,
    utcnow,
)


class TaskQueueBase(DeclarativeBase):
    """Standalone DeclarativeBase for task-queue tables.

    Merge ``TaskQueueBase.metadata`` into Alembic's ``target_metadata`` to
    manage migrations cleanly alongside your application's own tables.
    """


class Job(TaskQueueBase):
    """Main job record (``task_queue_worker_jobs``)."""

    __tablename__ = "task_queue_worker_jobs"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_job_id)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    arguments: Mapped[str] = mapped_column(Text, nullable=False, default="")
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retry: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    interval: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    status: Mapped[str] = mapped_column(String(255), nullable=False, default=JobStatus.QUEUEING)
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result: Mapped[str] = mapped_column(Text, nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    current_progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("idx_tqw_created_at", "created_at"),
        Index("idx_tqw_task_name", "task_name"),
        Index("idx_tqw_status", "status"),
        Index("idx_tqw_task_name_status", "task_name", "status"),
        Index("idx_tqw_task_name_status_created_at", "task_name", "status", "created_at"),
    )


class JobSummary(TaskQueueBase):
    """Per-task counters (``task_queue_worker_job_summaries``)."""

    __tablename__ = "task_queue_worker_job_summaries"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    success: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queueing: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retrying: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stopped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_loading: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    loading_message: Mapped[str] = mapped_column(String(255), nullable=False, default="")


class JobHistory(TaskQueueBase):
    """Retry attempt history per job (``task_queue_worker_job_histories``)."""

    __tablename__ = "task_queue_worker_job_histories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    error_stack: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result: Mapped[str] = mapped_column(Text, nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_tqw_job_id_history", "job_id"),
        Index("idx_tqw_start_at_history", "start_at"),
    )


class TaskQueueConfiguration(TaskQueueBase):
    """Runtime key/value configuration store (``task_queue_worker_configurations``)."""

    __tablename__ = "task_queue_worker_configurations"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    value: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


def _row_to_record(row: Job) -> JobRecord:
    return JobRecord(
        id=row.id,
        task_name=row.task_name,
        arguments=row.arguments,
        retries=row.retries,
        max_retry=row.max_retry,
        interval=row.interval,
        status=row.status,
        error=row.error,
        result=row.result,
        trace_id=row.trace_id,
        current_progress=row.current_progress,
        max_progress=row.max_progress,
        created_at=row.created_at,
        updated_at=row.updated_at,
        finished_at=row.finished_at,
    )


class SQLJobStore(JobStore):
    """SQLAlchemy 2.x async ``JobStore`` using the 4 canonical task-queue tables."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    @property
    def session_factory(self) -> Any:
        return self._session_factory

    async def recalc_summary(self, task_name: str) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                await self._recalc_summary_in_session(session, task_name)

    async def _recalc_summary_in_session(self, session: Any, task_name: str) -> None:
        counts: dict[str, int] = {}
        for status in ALL_JOB_STATUSES:
            cnt = int(
                (
                    await session.execute(
                        select(func.count()).where(Job.task_name == task_name, Job.status == status)
                    )
                ).scalar()
                or 0
            )
            counts[status] = cnt

        existing = await session.get(JobSummary, task_name)
        if existing is None:
            session.add(
                JobSummary(
                    id=task_name,
                    queueing=counts[JobStatus.QUEUEING],
                    retrying=counts[JobStatus.RETRYING],
                    success=counts[JobStatus.SUCCESS],
                    failure=counts[JobStatus.FAILURE],
                    stopped=counts[JobStatus.STOPPED],
                )
            )
        else:
            existing.queueing = counts[JobStatus.QUEUEING]
            existing.retrying = counts[JobStatus.RETRYING]
            existing.success = counts[JobStatus.SUCCESS]
            existing.failure = counts[JobStatus.FAILURE]
            existing.stopped = counts[JobStatus.STOPPED]

    async def enqueue(self, job: JobRecord) -> str:
        async with self._session_factory() as session:
            async with session.begin():
                orm_job = Job(
                    id=job.id,
                    task_name=job.task_name,
                    arguments=job.arguments,
                    retries=job.retries,
                    max_retry=job.max_retry,
                    interval=job.interval,
                    status=job.status,
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                )
                session.add(orm_job)
                await session.flush()
                job_id = orm_job.id
            async with session.begin():
                await self._recalc_summary_in_session(session, job.task_name)
        return job_id

    async def dequeue_batch(self, task_names: Iterable[str], limit: int = 50) -> list[JobRecord]:
        names = list(task_names)
        if not names:
            return []
        now = utcnow()
        async with self._session_factory() as session:
            async with session.begin():
                stmt = (
                    select(Job)
                    .where(Job.status == JobStatus.QUEUEING, Job.task_name.in_(names))
                    .order_by(Job.created_at.asc())
                    .limit(max(1, limit))
                    .with_for_update(skip_locked=True)
                )
                rows = list((await session.execute(stmt)).scalars().all())
                if not rows:
                    return []
                ids = [r.id for r in rows]
                await session.execute(
                    update(Job).where(Job.id.in_(ids)).values(status=JobStatus.RETRYING, updated_at=now)
                )
                records = [_row_to_record(r) for r in rows]
                for rec in records:
                    rec.status = JobStatus.RETRYING
                    rec.updated_at = now
                return records

    async def get_job(self, job_id: str) -> JobRecord | None:
        async with self._session_factory() as session:
            row = await session.get(Job, job_id)
            return _row_to_record(row) if row is not None else None

    def _build_query(self, flt: JobFilter) -> Any:
        stmt = select(Job)
        if flt.task_name:
            stmt = stmt.where(Job.task_name == flt.task_name)
        if flt.statuses:
            stmt = stmt.where(Job.status.in_(flt.statuses))
        if flt.search:
            stmt = stmt.where(Job.arguments.ilike(f"%{flt.search}%"))
        if flt.job_id:
            stmt = stmt.where(Job.id == flt.job_id)
        return stmt

    async def list_jobs(self, flt: JobFilter) -> JobPage:
        page = max(1, flt.page)
        limit = max(1, min(100, flt.limit))
        offset = (page - 1) * limit
        async with self._session_factory() as session:
            stmt = self._build_query(flt)
            total = int(
                (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
            )
            rows = list(
                (
                    await session.execute(
                        stmt.order_by(Job.created_at.desc()).offset(offset).limit(limit)
                    )
                ).scalars()
            )
        total_pages = max(1, (total + limit - 1) // limit)
        return JobPage(
            page=page,
            limit=limit,
            total_pages=total_pages,
            total_records=total,
            items=[_row_to_record(r) for r in rows],
        )

    async def count_jobs(self, flt: JobFilter) -> int:
        async with self._session_factory() as session:
            stmt = self._build_query(flt)
            return int(
                (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
            )

    async def finish_job(
        self,
        job: JobRecord,
        *,
        error: str | None,
        result: str,
        start_at: datetime,
        end_at: datetime,
    ) -> None:
        new_retries = job.retries + 1
        async with self._session_factory() as session:
            async with session.begin():
                session.add(
                    JobHistory(
                        job_id=job.id,
                        status=JobStatus.SUCCESS if error is None else JobStatus.FAILURE,
                        error=error or "",
                        result=result,
                        trace_id=job.trace_id,
                        start_at=start_at,
                        end_at=end_at,
                    )
                )
                if error is None:
                    await session.execute(
                        update(Job)
                        .where(Job.id == job.id)
                        .values(
                            status=JobStatus.SUCCESS,
                            finished_at=end_at,
                            updated_at=end_at,
                            retries=new_retries,
                            error="",
                            result=result,
                        )
                    )
                elif new_retries >= job.max_retry:
                    await session.execute(
                        update(Job)
                        .where(Job.id == job.id)
                        .values(
                            status=JobStatus.FAILURE,
                            finished_at=end_at,
                            updated_at=end_at,
                            retries=new_retries,
                            error=error,
                        )
                    )
                else:
                    await session.execute(
                        update(Job)
                        .where(Job.id == job.id)
                        .values(
                            status=JobStatus.QUEUEING,
                            updated_at=end_at,
                            retries=new_retries,
                            error=error,
                            finished_at=None,
                        )
                    )
            async with session.begin():
                await self._recalc_summary_in_session(session, job.task_name)

    async def persist_trace_id(self, job_id: str, trace_id: str) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    update(Job).where(Job.id == job_id).values(trace_id=trace_id, updated_at=utcnow())
                )

    async def retry_job(self, job_id: str) -> str | None:
        task_name: str | None = None
        async with self._session_factory() as session:
            async with session.begin():
                row = await session.get(Job, job_id)
                if row is not None:
                    task_name = row.task_name
                await session.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(
                        status=JobStatus.QUEUEING,
                        retries=0,
                        error="",
                        finished_at=None,
                        updated_at=utcnow(),
                    )
                )
            if task_name:
                async with session.begin():
                    await self._recalc_summary_in_session(session, task_name)
        return task_name

    async def retry_all(
        self,
        task_name: str,
        *,
        statuses: list[str] | None = None,
        search: str | None = None,
    ) -> int:
        async with self._session_factory() as session:
            async with session.begin():
                stmt = (
                    update(Job)
                    .where(Job.task_name == task_name)
                    .values(
                        status=JobStatus.QUEUEING,
                        retries=0,
                        error="",
                        finished_at=None,
                        updated_at=utcnow(),
                    )
                )
                if statuses:
                    stmt = stmt.where(Job.status.in_(statuses))
                if search:
                    stmt = stmt.where(Job.arguments.ilike(f"%{search}%"))
                res = await session.execute(stmt)
                updated = int(res.rowcount or 0)
            async with session.begin():
                await self._recalc_summary_in_session(session, task_name)
        return updated

    async def stop_job(self, job_id: str) -> str | None:
        task_name: str | None = None
        async with self._session_factory() as session:
            async with session.begin():
                row = await session.get(Job, job_id)
                if row is not None:
                    task_name = row.task_name
                await session.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(status=JobStatus.STOPPED, updated_at=utcnow())
                )
            if task_name:
                async with session.begin():
                    await self._recalc_summary_in_session(session, task_name)
        return task_name

    async def stop_all(self, task_name: str) -> int:
        async with self._session_factory() as session:
            async with session.begin():
                res = await session.execute(
                    update(Job)
                    .where(
                        Job.task_name == task_name,
                        Job.status.in_([JobStatus.QUEUEING, JobStatus.RETRYING]),
                    )
                    .values(status=JobStatus.STOPPED, updated_at=utcnow())
                )
                updated = int(res.rowcount or 0)
            async with session.begin():
                await self._recalc_summary_in_session(session, task_name)
        return updated

    async def delete_job(self, job_id: str) -> str | None:
        task_name: str | None = None
        async with self._session_factory() as session:
            async with session.begin():
                row = await session.get(Job, job_id)
                if row is not None:
                    task_name = row.task_name
                await session.execute(delete(Job).where(Job.id == job_id))
            if task_name:
                async with session.begin():
                    await self._recalc_summary_in_session(session, task_name)
        return task_name

    async def clean_jobs(
        self,
        task_name: str,
        *,
        statuses: list[str] | None = None,
        search: str | None = None,
    ) -> int:
        async with self._session_factory() as session:
            async with session.begin():
                stmt = delete(Job).where(Job.task_name == task_name)
                if statuses:
                    stmt = stmt.where(Job.status.in_(statuses))
                if search:
                    stmt = stmt.where(Job.arguments.ilike(f"%{search}%"))
                res = await session.execute(stmt)
                deleted = int(res.rowcount or 0)
            async with session.begin():
                await self._recalc_summary_in_session(session, task_name)
        return deleted

    async def init_summaries(self, task_names: Iterable[str]) -> None:
        names = list(task_names)
        if not names:
            return
        async with self._session_factory() as session:
            async with session.begin():
                for name in names:
                    await self._recalc_summary_in_session(session, name)

    async def get_summaries(self, task_names: Iterable[str]) -> dict[str, TaskCounts]:
        names = list(task_names)
        async with self._session_factory() as session:
            rows = list((await session.execute(select(JobSummary))).scalars())
        summary_map = {r.id: r for r in rows}
        result: dict[str, TaskCounts] = {}
        for name in names:
            s = summary_map.get(name)
            result[name] = TaskCounts(
                queueing=s.queueing if s else 0,
                retrying=s.retrying if s else 0,
                success=s.success if s else 0,
                failure=s.failure if s else 0,
                stopped=s.stopped if s else 0,
            )
        return result
