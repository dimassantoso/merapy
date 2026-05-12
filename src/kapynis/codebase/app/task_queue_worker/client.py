"""Client API for enqueuing tasks. Used by usecases."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from kapynis.codebase.app.task_queue_worker.model import Task, TaskStatus
from kapynis.repository.transaction import current_session


class TaskQueueClient:
    """Persist a task for the worker to pick up.

    Reuses the ambient SQL transaction if the caller is inside
    ``with_transaction(...)``; otherwise opens a one-shot session.
    """

    __slots__ = ("_session_factory",)

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def enqueue(
        self,
        name: str,
        payload: bytes = b"",
        *,
        delay: timedelta | None = None,
        max_attempts: int = 5,
    ) -> int:
        scheduled = datetime.now(tz=timezone.utc) + (delay or timedelta())
        task = Task(
            name=name,
            payload=payload,
            scheduled_at=scheduled,
            max_attempts=max_attempts,
            status=TaskStatus.PENDING,
        )
        async with current_session(self._session_factory) as session:
            session.add(task)
            await session.flush()
            return task.id
