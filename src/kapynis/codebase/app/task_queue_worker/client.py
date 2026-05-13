"""Client API for enqueuing tasks. Used by usecases."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from kapynis.codebase.app.task_queue_worker.model import Job, JobStatus
from kapynis.repository.transaction import current_session


class TaskQueueClient:
    """Persist a task for the worker to pick up.

    Reuses the ambient SQL transaction if the caller is inside
    ``with_transaction(...)``; otherwise opens a one-shot session.

    Example::

        client = TaskQueueClient(deps.sql_db().session_factory())
        job_id = await client.enqueue("auth_task", args={"user_id": 1}, max_retry=3)
    """

    __slots__ = ("_session_factory",)

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def enqueue(
        self,
        task_name: str,
        args: dict | str | bytes = "",
        *,
        max_retry: int = 5,
        interval: str = "",
        delay: timedelta | None = None,
    ) -> str:
        """Enqueue a job and return its ID (UUID string).

        Args:
            task_name:  Must match a registered handler pattern.
            args:       Job arguments — dict (JSON-serialised), str, or bytes.
            max_retry:  Maximum retry attempts before marking FAILURE.
            interval:   Optional cron/interval expression (informational).
            delay:      Schedule the job in the future by this timedelta.
        """
        if isinstance(args, dict):
            arguments = json.dumps(args)
        elif isinstance(args, bytes):
            arguments = args.decode()
        else:
            arguments = str(args)

        job = Job(
            task_name=task_name,
            arguments=arguments,
            max_retry=max_retry,
            interval=interval,
            status=JobStatus.QUEUEING,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        async with current_session(self._session_factory) as session:
            session.add(job)
            await session.flush()
            return job.id
