"""SQLAlchemy models for the task-queue worker (re-exported from ``merapy_taskqueue``)."""

from __future__ import annotations

try:
    from merapy_taskqueue.store.sql import (
        Job,
        JobHistory,
        JobSummary,
        TaskQueueBase,
        TaskQueueConfiguration,
    )
    from merapy_taskqueue.types import JobStatus
except ImportError as exc:
    raise ImportError(
        "merapy-taskqueue is required for task_queue_worker models. "
        "Install it with: pip install 'merapy[taskqueue]' or pip install merapy-taskqueue[sql,metrics]"
    ) from exc

__all__ = [
    "Job",
    "JobHistory",
    "JobStatus",
    "JobSummary",
    "TaskQueueBase",
    "TaskQueueConfiguration",
]
