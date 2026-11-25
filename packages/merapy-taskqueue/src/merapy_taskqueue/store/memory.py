"""Zero-dependency in-memory ``JobStore`` for dev, scripts, and tests."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from copy import deepcopy
from datetime import datetime

from merapy_taskqueue.store.base import JobStore
from merapy_taskqueue.types import JobFilter, JobPage, JobRecord, JobStatus, TaskCounts, utcnow


class MemoryJobStore(JobStore):
    """Async-safe in-memory ``JobStore`` with full dashboard support."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._jobs: dict[str, JobRecord] = {}

    async def enqueue(self, job: JobRecord) -> str:
        async with self._lock:
            self._jobs[job.id] = deepcopy(job)
            return job.id

    async def dequeue_batch(self, task_names: Iterable[str], limit: int = 50) -> list[JobRecord]:
        allowed = set(task_names)
        if not allowed:
            return []
        now = utcnow()
        async with self._lock:
            candidates = [
                j
                for j in self._jobs.values()
                if j.status == JobStatus.QUEUEING and j.task_name in allowed
            ]
            candidates.sort(key=lambda j: j.created_at)
            picked = candidates[: max(1, limit)]
            for job in picked:
                job.status = JobStatus.RETRYING
                job.updated_at = now
            return [deepcopy(j) for j in picked]

    async def get_job(self, job_id: str) -> JobRecord | None:
        async with self._lock:
            job = self._jobs.get(job_id)
            return deepcopy(job) if job is not None else None

    def _filter_locked(self, flt: JobFilter) -> list[JobRecord]:
        items = list(self._jobs.values())
        if flt.task_name:
            items = [j for j in items if j.task_name == flt.task_name]
        if flt.statuses:
            status_set = set(flt.statuses)
            items = [j for j in items if j.status in status_set]
        if flt.search:
            needle = flt.search.lower()
            items = [j for j in items if needle in j.arguments.lower()]
        if flt.job_id:
            items = [j for j in items if j.id == flt.job_id]
        items.sort(key=lambda j: j.created_at, reverse=True)
        return items

    async def list_jobs(self, flt: JobFilter) -> JobPage:
        page = max(1, flt.page)
        limit = max(1, min(100, flt.limit))
        offset = (page - 1) * limit
        async with self._lock:
            matched = self._filter_locked(flt)
            total = len(matched)
            sliced = [deepcopy(j) for j in matched[offset : offset + limit]]
        total_pages = max(1, (total + limit - 1) // limit)
        return JobPage(
            page=page,
            limit=limit,
            total_pages=total_pages,
            total_records=total,
            items=sliced,
        )

    async def count_jobs(self, flt: JobFilter) -> int:
        async with self._lock:
            return len(self._filter_locked(flt))

    async def finish_job(
        self,
        job: JobRecord,
        *,
        error: str | None,
        result: str,
        start_at: datetime,
        end_at: datetime,
    ) -> None:
        del start_at
        async with self._lock:
            stored = self._jobs.get(job.id)
            if stored is None:
                return
            new_retries = stored.retries + 1
            stored.retries = new_retries
            stored.updated_at = end_at
            if error is None:
                stored.status = JobStatus.SUCCESS
                stored.finished_at = end_at
                stored.error = ""
                stored.result = result
            elif new_retries >= stored.max_retry:
                stored.status = JobStatus.FAILURE
                stored.finished_at = end_at
                stored.error = error
            else:
                stored.status = JobStatus.QUEUEING
                stored.finished_at = None
                stored.error = error

    async def persist_trace_id(self, job_id: str, trace_id: str) -> None:
        async with self._lock:
            stored = self._jobs.get(job_id)
            if stored is not None:
                stored.trace_id = trace_id
                stored.updated_at = utcnow()

    async def retry_job(self, job_id: str) -> str | None:
        async with self._lock:
            stored = self._jobs.get(job_id)
            if stored is None:
                return None
            stored.status = JobStatus.QUEUEING
            stored.retries = 0
            stored.error = ""
            stored.finished_at = None
            stored.updated_at = utcnow()
            return stored.task_name

    async def retry_all(
        self,
        task_name: str,
        *,
        statuses: list[str] | None = None,
        search: str | None = None,
    ) -> int:
        now = utcnow()
        count = 0
        async with self._lock:
            for j in self._jobs.values():
                if j.task_name != task_name:
                    continue
                if statuses and j.status not in statuses:
                    continue
                if search and search.lower() not in j.arguments.lower():
                    continue
                j.status = JobStatus.QUEUEING
                j.retries = 0
                j.error = ""
                j.finished_at = None
                j.updated_at = now
                count += 1
        return count

    async def stop_job(self, job_id: str) -> str | None:
        async with self._lock:
            stored = self._jobs.get(job_id)
            if stored is None:
                return None
            stored.status = JobStatus.STOPPED
            stored.updated_at = utcnow()
            return stored.task_name

    async def stop_all(self, task_name: str) -> int:
        now = utcnow()
        count = 0
        async with self._lock:
            for j in self._jobs.values():
                if j.task_name == task_name and j.status in (JobStatus.QUEUEING, JobStatus.RETRYING):
                    j.status = JobStatus.STOPPED
                    j.updated_at = now
                    count += 1
        return count

    async def delete_job(self, job_id: str) -> str | None:
        async with self._lock:
            stored = self._jobs.pop(job_id, None)
            return stored.task_name if stored is not None else None

    async def clean_jobs(
        self,
        task_name: str,
        *,
        statuses: list[str] | None = None,
        search: str | None = None,
    ) -> int:
        async with self._lock:
            to_delete = [
                jid
                for jid, j in self._jobs.items()
                if j.task_name == task_name
                and (not statuses or j.status in statuses)
                and (not search or search.lower() in j.arguments.lower())
            ]
            for jid in to_delete:
                del self._jobs[jid]
            return len(to_delete)

    async def init_summaries(self, task_names: Iterable[str]) -> None:
        del task_names

    async def get_summaries(self, task_names: Iterable[str]) -> dict[str, TaskCounts]:
        names = list(task_names)
        result = {name: TaskCounts() for name in names}
        async with self._lock:
            for j in self._jobs.values():
                counts = result.get(j.task_name)
                if counts is None:
                    continue
                if j.status == JobStatus.QUEUEING:
                    counts.queueing += 1
                elif j.status == JobStatus.RETRYING:
                    counts.retrying += 1
                elif j.status == JobStatus.SUCCESS:
                    counts.success += 1
                elif j.status == JobStatus.FAILURE:
                    counts.failure += 1
                elif j.status == JobStatus.STOPPED:
                    counts.stopped += 1
        return result
