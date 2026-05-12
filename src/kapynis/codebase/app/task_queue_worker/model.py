"""SQLAlchemy model for the task-queue table."""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class TaskBase(DeclarativeBase):
    """Standalone Base for the task table. Kept separate from the user's
    ``pkg/shared/domain`` Base so Alembic in the generated service can
    autogenerate without conflict.
    """


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class Task(TaskBase):
    __tablename__ = "kapynis_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    payload: Mapped[bytes] = mapped_column(default=b"")
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="kapynis_task_status"),
        default=TaskStatus.PENDING,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
