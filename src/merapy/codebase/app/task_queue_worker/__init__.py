"""Persistent task-queue worker.

v1 supports:

* Persisting jobs to SQL (SQLAlchemy).
* Poll-based job dispatch with retry and backoff.
* Status: QUEUEING / RETRYING / SUCCESS / FAILURE / STOPPED.
"""* Polling for due jobs.
* Retry on failure with exponential backoff.
* Status: pending / running / done / failed.

NOT included in v1 (roadmap):

* GraphQL admin UI.
* Mongo / Redis backends — SQL only.
* Cross-process job scheduling primitives beyond polling.

Use Celery / Dramatiq / arq if you need a battle-tested queue.
"""

from merapy.codebase.app.task_queue_worker.worker import TaskQueueWorker
from merapy.codebase.app.task_queue_worker.client import TaskQueueClient

__all__ = ["TaskQueueClient", "TaskQueueWorker"]
