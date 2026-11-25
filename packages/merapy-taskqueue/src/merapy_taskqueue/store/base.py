"""Abstract ``JobStore`` interface for pluggable task-queue persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime

from merapy_taskqueue.types import JobFilter, JobPage, JobRecord, TaskCounts


class JobStore(ABC):
    """Storage contract implemented by Memory, SQL, Mongo, and Redis job stores.

    Both the worker loop and the GraphQL dashboard operate exclusively against
    this interface so any backend gets full dashboard functionality.
    """

    @abstractmethod
    async def enqueue(self, job: JobRecord) -> str:
        """Persist a new job and return its ID."""

    @abstractmethod
    async def dequeue_batch(self, task_names: Iterable[str], limit: int = 50) -> list[JobRecord]:
        """Claim up to ``limit`` QUEUEING jobs for ``task_names`` and mark them RETRYING."""

    @abstractmethod
    async def get_job(self, job_id: str) -> JobRecord | None:
        """Fetch a single job by ID."""

    @abstractmethod
    async def list_jobs(self, flt: JobFilter) -> JobPage:
        """Return paginated jobs matching ``flt``, ordered newest first."""

    @abstractmethod
    async def count_jobs(self, flt: JobFilter) -> int:
        """Return count of jobs matching ``flt``."""

    @abstractmethod
    async def finish_job(
        self,
        job: JobRecord,
        *,
        error: str | None,
        result: str,
        start_at: datetime,
        end_at: datetime,
    ) -> None:
        """Finalize a job attempt (SUCCESS, FAILURE, or re-queue for retry) and record history."""

    @abstractmethod
    async def persist_trace_id(self, job_id: str, trace_id: str) -> None:
        """Attach an OpenTelemetry trace ID to a running job."""

    @abstractmethod
    async def retry_job(self, job_id: str) -> str | None:
        """Reset a single job to QUEUEING with retries=0. Returns task_name if found."""

    @abstractmethod
    async def retry_all(
        self,
        task_name: str,
        *,
        statuses: list[str] | None = None,
        search: str | None = None,
    ) -> int:
        """Reset matching jobs for ``task_name`` to QUEUEING. Empty statuses retries all."""

    @abstractmethod
    async def stop_job(self, job_id: str) -> str | None:
        """Mark a single job as STOPPED. Returns task_name if found."""

    @abstractmethod
    async def stop_all(self, task_name: str) -> int:
        """Mark all QUEUEING/RETRYING jobs for ``task_name`` as STOPPED."""

    @abstractmethod
    async def delete_job(self, job_id: str) -> str | None:
        """Permanently delete a single job. Returns task_name if found."""

    @abstractmethod
    async def clean_jobs(
        self,
        task_name: str,
        *,
        statuses: list[str] | None = None,
        search: str | None = None,
    ) -> int:
        """Permanently delete matching jobs for ``task_name``."""

    @abstractmethod
    async def init_summaries(self, task_names: Iterable[str]) -> None:
        """Ensure summary entries exist for all registered task names."""

    @abstractmethod
    async def get_summaries(self, task_names: Iterable[str]) -> dict[str, TaskCounts]:
        """Return per-status counts keyed by task name."""

    async def close(self) -> None:
        """Optional cleanup hook called on worker shutdown."""
