"""SQLAlchemy models for the task-queue worker.

Table names and column names mirror candi's task_queue_worker SQL schema
(persistent_sql_tools.go) so the kapynis-taskqueue-dashboard can connect
to either a candi or kapynis service without schema changes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, Index, Integer, String, Text
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class TaskQueueBase(DeclarativeBase):
    """Standalone Base for task-queue tables.

    Kept separate from the service's ``pkg/shared/domain`` Base so alembic
    autogenerate in the generated service can include these tables by merging
    metadata (see alembic/env.py).
    """


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Status constants — match candi's JobStatusEnum exactly
# ---------------------------------------------------------------------------

class JobStatus:
    QUEUEING = "QUEUEING"
    RETRYING = "RETRYING"
    SUCCESS  = "SUCCESS"
    FAILURE  = "FAILURE"
    STOPPED  = "STOPPED"


# ---------------------------------------------------------------------------
# task_queue_worker_jobs
# ---------------------------------------------------------------------------

class Job(TaskQueueBase):
    """Mirrors candi's ``task_queue_worker_jobs`` table."""

    __tablename__ = "task_queue_worker_jobs"

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, default=_new_id
    )
    task_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    arguments: Mapped[str] = mapped_column(Text, nullable=False, default="")
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retry: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    interval: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
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


# ---------------------------------------------------------------------------
# task_queue_worker_job_summaries
# ---------------------------------------------------------------------------

class JobSummary(TaskQueueBase):
    """Mirrors candi's ``task_queue_worker_job_summaries`` table.

    ``id`` is the task_name — one row per registered task.
    """

    __tablename__ = "task_queue_worker_job_summaries"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)  # = task_name
    success: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queueing: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retrying: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stopped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_loading: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    loading_message: Mapped[str] = mapped_column(String(255), nullable=False, default="")


# ---------------------------------------------------------------------------
# task_queue_worker_job_histories
# ---------------------------------------------------------------------------

class JobHistory(TaskQueueBase):
    """Mirrors candi's ``task_queue_worker_job_histories`` table."""

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


# ---------------------------------------------------------------------------
# task_queue_worker_configurations
# ---------------------------------------------------------------------------

class TaskQueueConfiguration(TaskQueueBase):
    """Mirrors candi's ``task_queue_worker_configurations`` table."""

    __tablename__ = "task_queue_worker_configurations"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    value: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
