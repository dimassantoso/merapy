"""Redis async ``JobStore`` with full dashboard query and mutation support."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from merapy_taskqueue.store.base import JobStore
from merapy_taskqueue.types import JobFilter, JobPage, JobRecord, JobStatus, TaskCounts, utcnow


def _decode(val: Any) -> str:
    return val.decode("utf-8") if isinstance(val, bytes) else str(val)


class RedisJobStore(JobStore):
    """Stores task-queue jobs in Redis hashes + sorted-set index."""

    def __init__(self, redis_client: Any, key_prefix: str = "merapy_tq") -> None:
        self._redis = redis_client
        self._prefix = key_prefix

    def _job_key(self, job_id: str) -> str:
        return f"{self._prefix}:job:{job_id}"

    def _all_key(self) -> str:
        return f"{self._prefix}:all"

    def _queue_key(self, task_name: str) -> str:
        return f"{self._prefix}:queue:{task_name}"

    async def _load_job(self, job_id: str) -> JobRecord | None:
        raw = await self._redis.hgetall(self._job_key(job_id))
        if not raw:
            return None
        d: dict[str, Any] = {_decode(k): _decode(v) for k, v in raw.items()}
        if not d.get("finished_at"):
            d["finished_at"] = None
        return JobRecord.from_dict(d)

    async def _save_job(self, job: JobRecord) -> None:
        mapping = {k: ("" if v is None else str(v)) for k, v in job.to_dict().items()}
        pipe = self._redis.pipeline()
        pipe.hset(self._job_key(job.id), mapping=mapping)
        pipe.zadd(self._all_key(), {job.id: job.created_at.timestamp()})
        if job.status == JobStatus.QUEUEING:
            pipe.zadd(self._queue_key(job.task_name), {job.id: job.created_at.timestamp()})
        else:
            pipe.zrem(self._queue_key(job.task_name), job.id)
        await pipe.execute()

    async def enqueue(self, job: JobRecord) -> str:
        await self._save_job(job)
        return job.id

    async def dequeue_batch(self, task_names: Iterable[str], limit: int = 50) -> list[JobRecord]:
        names = list(task_names)
        if not names:
            return []
        picked: list[JobRecord] = []
        per_task = max(1, limit // len(names))
        now = utcnow()
        for task_name in names:
            ids = await self._redis.zrange(self._queue_key(task_name), 0, per_task - 1)
            for raw_id in ids:
                job = await self._load_job(_decode(raw_id))
                if job is None or job.status != JobStatus.QUEUEING:
                    await self._redis.zrem(self._queue_key(task_name), raw_id)
                    continue
                job.status = JobStatus.RETRYING
                job.updated_at = now
                await self._save_job(job)
                picked.append(job)
        return picked

    async def get_job(self, job_id: str) -> JobRecord | None:
        return await self._load_job(job_id)

    async def _all_matching(self, flt: JobFilter) -> list[JobRecord]:
        if flt.job_id:
            one = await self._load_job(flt.job_id)
            return [one] if one is not None else []
        ids = await self._redis.zrevrange(self._all_key(), 0, -1)
        out: list[JobRecord] = []
        status_set = set(flt.statuses) if flt.statuses else None
        needle = flt.search.lower() if flt.search else None
        for raw_id in ids:
            job = await self._load_job(_decode(raw_id))
            if job is None:
                continue
            if flt.task_name and job.task_name != flt.task_name:
                continue
            if status_set is not None and job.status not in status_set:
                continue
            if needle is not None and needle not in job.arguments.lower():
                continue
            out.append(job)
        return out

    async def list_jobs(self, flt: JobFilter) -> JobPage:
        page = max(1, flt.page)
        limit = max(1, min(100, flt.limit))
        offset = (page - 1) * limit
        matched = await self._all_matching(flt)
        total = len(matched)
        total_pages = max(1, (total + limit - 1) // limit)
        return JobPage(
            page=page,
            limit=limit,
            total_pages=total_pages,
            total_records=total,
            items=matched[offset : offset + limit],
        )

    async def count_jobs(self, flt: JobFilter) -> int:
        return len(await self._all_matching(flt))

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
        stored = await self._load_job(job.id)
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
        await self._save_job(stored)

    async def persist_trace_id(self, job_id: str, trace_id: str) -> None:
        await self._redis.hset(
            self._job_key(job_id),
            mapping={"trace_id": trace_id, "updated_at": utcnow().isoformat()},
        )

    async def retry_job(self, job_id: str) -> str | None:
        job = await self._load_job(job_id)
        if job is None:
            return None
        job.status = JobStatus.QUEUEING
        job.retries = 0
        job.error = ""
        job.finished_at = None
        job.updated_at = utcnow()
        await self._save_job(job)
        return job.task_name

    async def retry_all(
        self,
        task_name: str,
        *,
        statuses: list[str] | None = None,
        search: str | None = None,
    ) -> int:
        matched = await self._all_matching(JobFilter(task_name=task_name, statuses=statuses, search=search))
        now = utcnow()
        for job in matched:
            job.status = JobStatus.QUEUEING
            job.retries = 0
            job.error = ""
            job.finished_at = None
            job.updated_at = now
            await self._save_job(job)
        return len(matched)

    async def stop_job(self, job_id: str) -> str | None:
        job = await self._load_job(job_id)
        if job is None:
            return None
        job.status = JobStatus.STOPPED
        job.updated_at = utcnow()
        await self._save_job(job)
        return job.task_name

    async def stop_all(self, task_name: str) -> int:
        matched = await self._all_matching(
            JobFilter(task_name=task_name, statuses=[JobStatus.QUEUEING, JobStatus.RETRYING])
        )
        now = utcnow()
        for job in matched:
            job.status = JobStatus.STOPPED
            job.updated_at = now
            await self._save_job(job)
        return len(matched)

    async def delete_job(self, job_id: str) -> str | None:
        job = await self._load_job(job_id)
        if job is None:
            return None
        pipe = self._redis.pipeline()
        pipe.delete(self._job_key(job_id))
        pipe.zrem(self._all_key(), job_id)
        pipe.zrem(self._queue_key(job.task_name), job_id)
        await pipe.execute()
        return job.task_name

    async def clean_jobs(
        self,
        task_name: str,
        *,
        statuses: list[str] | None = None,
        search: str | None = None,
    ) -> int:
        matched = await self._all_matching(JobFilter(task_name=task_name, statuses=statuses, search=search))
        for job in matched:
            await self.delete_job(job.id)
        return len(matched)

    async def init_summaries(self, task_names: Iterable[str]) -> None:
        del task_names

    async def get_summaries(self, task_names: Iterable[str]) -> dict[str, TaskCounts]:
        names = list(task_names)
        result = {name: TaskCounts() for name in names}
        matched = await self._all_matching(JobFilter())
        for job in matched:
            counts = result.get(job.task_name)
            if counts is None:
                continue
            if job.status == JobStatus.QUEUEING:
                counts.queueing += 1
            elif job.status == JobStatus.RETRYING:
                counts.retrying += 1
            elif job.status == JobStatus.SUCCESS:
                counts.success += 1
            elif job.status == JobStatus.FAILURE:
                counts.failure += 1
            elif job.status == JobStatus.STOPPED:
                counts.stopped += 1
        return result
