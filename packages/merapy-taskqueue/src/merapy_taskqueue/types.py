"""Core data types for standalone ``merapy-taskqueue``."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def new_job_id() -> str:
    return str(uuid.uuid4())


class JobStatus(StrEnum):
    """Canonical task-queue job status strings (uppercase, candi-compatible)."""

    QUEUEING = "QUEUEING"
    RETRYING = "RETRYING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    STOPPED = "STOPPED"


ALL_JOB_STATUSES: tuple[str, ...] = (
    JobStatus.QUEUEING,
    JobStatus.RETRYING,
    JobStatus.SUCCESS,
    JobStatus.FAILURE,
    JobStatus.STOPPED,
)


@dataclass(slots=True)
class JobRecord:
    """Backend-agnostic representation of a queued job."""

    id: str = field(default_factory=new_job_id)
    task_name: str = ""
    arguments: str = ""
    retries: int = 0
    max_retry: int = 5
    interval: str = ""
    status: str = JobStatus.QUEUEING
    error: str = ""
    result: str = ""
    trace_id: str = ""
    current_progress: int = 0
    max_progress: int = 0
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
    finished_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_name": self.task_name,
            "arguments": self.arguments,
            "retries": self.retries,
            "max_retry": self.max_retry,
            "interval": self.interval,
            "status": self.status,
            "error": self.error,
            "result": self.result,
            "trace_id": self.trace_id,
            "current_progress": self.current_progress,
            "max_progress": self.max_progress,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobRecord:
        created_raw = data.get("created_at")
        updated_raw = data.get("updated_at")
        finished_raw = data.get("finished_at")
        return cls(
            id=str(data.get("id") or new_job_id()),
            task_name=str(data.get("task_name", "")),
            arguments=str(data.get("arguments", "")),
            retries=int(data.get("retries", 0) or 0),
            max_retry=int(data.get("max_retry", 5) or 5),
            interval=str(data.get("interval", "")),
            status=str(data.get("status", JobStatus.QUEUEING)),
            error=str(data.get("error", "")),
            result=str(data.get("result", "")),
            trace_id=str(data.get("trace_id", "")),
            current_progress=int(data.get("current_progress", 0) or 0),
            max_progress=int(data.get("max_progress", 0) or 0),
            created_at=(
                datetime.fromisoformat(created_raw) if isinstance(created_raw, str) and created_raw else utcnow()
            ),
            updated_at=(
                datetime.fromisoformat(updated_raw) if isinstance(updated_raw, str) and updated_raw else utcnow()
            ),
            finished_at=(
                datetime.fromisoformat(finished_raw) if isinstance(finished_raw, str) and finished_raw else None
            ),
        )


@dataclass(slots=True)
class JobFilter:
    """Filter parameters for querying or bulk-mutating jobs."""

    page: int = 1
    limit: int = 20
    task_name: str | None = None
    search: str | None = None
    statuses: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None
    job_id: str | None = None


@dataclass(slots=True)
class JobPage:
    """Paginated job query response."""

    page: int
    limit: int
    total_pages: int
    total_records: int
    items: list[JobRecord]


@dataclass(slots=True)
class TaskCounts:
    """Per-status counters for a task."""

    queueing: int = 0
    retrying: int = 0
    success: int = 0
    failure: int = 0
    stopped: int = 0

    @property
    def total(self) -> int:
        return self.queueing + self.retrying + self.success + self.failure + self.stopped


@dataclass(slots=True)
class TaskSummary:
    """Summary entry shown on the main dashboard table."""

    name: str
    module_name: str
    counts: TaskCounts = field(default_factory=TaskCounts)
    is_loading: bool = False


@dataclass(slots=True)
class TaskContext:
    """Execution context passed to standalone task handlers."""

    job_id: str
    task_name: str
    arguments: str
    retries: int
    max_retry: int
    interval: str = ""
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def body(self) -> bytes:
        return self.arguments.encode("utf-8")


@dataclass(slots=True)
class DashboardConfig:
    """Metadata and server settings displayed by the Task Queue Dashboard."""

    host: str = "0.0.0.0"
    port: int = 8080
    service_name: str = ""
    service_version: str = ""
    framework_version: str = ""
    build_number: str = ""
    git_commit: str = ""
    build_date: str = ""
    static_dir: str | None = None
