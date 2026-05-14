"""Persistent task-queue worker. Minimal SQL-backed version.

A simplified port of candi's ``task_queue_worker``. v1 supports:

* Persisting jobs to a ``kapynis_tasks`` table (SQLAlchemy).
* Polling for due jobs.
* Retry on failure with exponential backoff.
* Status: pending / running / done / failed.

NOT included in v1 (candi's full feature set):

* GraphQL admin UI.
* Mongo / Redis backends — SQL only.
* Cross-process job scheduling primitives beyond polling.

Use Celery / Dramatiq / arq if you need a battle-tested queue.
"""

from merapy.codebase.app.task_queue_worker.worker import TaskQueueWorker
from merapy.codebase.app.task_queue_worker.client import TaskQueueClient

__all__ = ["TaskQueueClient", "TaskQueueWorker"]
