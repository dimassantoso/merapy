"""Persistent task-queue worker.

Supports:

* SQL-backed job persistence (SQLAlchemy async).
* Poll-based dispatch with retry and exponential backoff.
* Status: QUEUEING / RETRYING / SUCCESS / FAILURE / STOPPED.

Roadmap:
* Mongo / Redis backends (SQL only for now).
* Cross-process scheduling primitives beyond polling.
"""

from merapy.codebase.app.task_queue_worker.worker import TaskQueueWorker
from merapy.codebase.app.task_queue_worker.client import TaskQueueClient

__all__ = ["TaskQueueClient", "TaskQueueWorker"]
