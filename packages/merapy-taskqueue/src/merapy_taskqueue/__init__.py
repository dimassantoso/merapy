"""Standalone async Python task queue with embedded Vite + Preact dashboard."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from merapy_taskqueue.dashboard import TaskQueueDashboard, build_schema, find_static_dir
from merapy_taskqueue.store.base import JobStore
from merapy_taskqueue.store.memory import MemoryJobStore
from merapy_taskqueue.types import (
    ALL_JOB_STATUSES,
    DashboardConfig,
    JobFilter,
    JobPage,
    JobRecord,
    JobStatus,
    TaskContext,
    TaskCounts,
    TaskSummary,
)
from merapy_taskqueue.worker import TaskQueue

__version__ = "0.1.0"

if TYPE_CHECKING:
    from merapy_taskqueue.store.mongo import MongoJobStore
    from merapy_taskqueue.store.redis import RedisJobStore
    from merapy_taskqueue.store.sql import (
        Job,
        JobHistory,
        JobSummary,
        SQLJobStore,
        TaskQueueBase,
        TaskQueueConfiguration,
    )

__all__ = [
    "ALL_JOB_STATUSES",
    "DashboardConfig",
    "Job",
    "JobFilter",
    "JobHistory",
    "JobPage",
    "JobRecord",
    "JobStatus",
    "JobStore",
    "JobSummary",
    "MemoryJobStore",
    "MongoJobStore",
    "RedisJobStore",
    "SQLJobStore",
    "TaskContext",
    "TaskCounts",
    "TaskQueue",
    "TaskQueueBase",
    "TaskQueueConfiguration",
    "TaskQueueDashboard",
    "TaskSummary",
    "__version__",
    "build_schema",
    "find_static_dir",
]

_LAZY_SQL = {
    "Job",
    "JobHistory",
    "JobSummary",
    "SQLJobStore",
    "TaskQueueBase",
    "TaskQueueConfiguration",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_SQL:
        from merapy_taskqueue.store import sql  # noqa: PLC0415

        return getattr(sql, name)
    if name == "MongoJobStore":
        from merapy_taskqueue.store.mongo import MongoJobStore  # noqa: PLC0415

        return MongoJobStore
    if name == "RedisJobStore":
        from merapy_taskqueue.store.redis import RedisJobStore  # noqa: PLC0415

        return RedisJobStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
