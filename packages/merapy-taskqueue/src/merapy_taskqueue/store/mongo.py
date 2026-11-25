"""MongoDB (Motor) ``JobStore`` with full dashboard query and mutation support."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from merapy_taskqueue.store.base import JobStore
from merapy_taskqueue.types import JobFilter, JobPage, JobRecord, JobStatus, TaskCounts, utcnow


class MongoJobStore(JobStore):
    """Stores task-queue jobs in a MongoDB collection via Motor."""

    def __init__(self, mongo_db: Any, collection: str = "task_queue_worker_jobs") -> None:
        self._col = mongo_db[collection]

    def _query_doc(self, flt: JobFilter) -> dict[str, Any]:
        query: dict[str, Any] = {}
        if flt.task_name:
            query["task_name"] = flt.task_name
        if flt.statuses:
            query["status"] = {"$in": flt.statuses}
        if flt.search:
            query["arguments"] = {"$regex": re.escape(flt.search), "$options": "i"}
        if flt.job_id:
            query["_id"] = flt.job_id
        return query

    async def enqueue(self, job: JobRecord) -> str:
        doc = job.to_dict()
        doc["_id"] = doc.pop("id")
        await self._col.insert_one(doc)
        return job.id

    async def dequeue_batch(self, task_names: Iterable[str], limit: int = 50) -> list[JobRecord]:
        names = list(task_names)
        if not names:
            return []
        now = utcnow()
        cursor = self._col.find(
            {"task_name": {"$in": names}, "status": JobStatus.QUEUEING},
            sort=[("created_at", 1)],
            limit=max(1, limit),
        )
        jobs: list[JobRecord] = []
        async for doc in cursor:
            doc["id"] = doc.pop("_id")
            rec = JobRecord.from_dict(doc)
            rec.status = JobStatus.RETRYING
            rec.updated_at = now
            jobs.append(rec)
        if jobs:
            await self._col.update_many(
                {"_id": {"$in": [j.id for j in jobs]}},
                {"$set": {"status": JobStatus.RETRYING, "updated_at": now.isoformat()}},
            )
        return jobs

    async def get_job(self, job_id: str) -> JobRecord | None:
        doc = await self._col.find_one({"_id": job_id})
        if doc is None:
            return None
        doc["id"] = doc.pop("_id")
        return JobRecord.from_dict(doc)

    async def list_jobs(self, flt: JobFilter) -> JobPage:
        page = max(1, flt.page)
        limit = max(1, min(100, flt.limit))
        offset = (page - 1) * limit
        query = self._query_doc(flt)
        total = int(await self._col.count_documents(query))
        cursor = self._col.find(query, sort=[("created_at", -1)], skip=offset, limit=limit)
        items: list[JobRecord] = []
        async for doc in cursor:
            doc["id"] = doc.pop("_id")
            items.append(JobRecord.from_dict(doc))
        total_pages = max(1, (total + limit - 1) // limit)
        return JobPage(page=page, limit=limit, total_pages=total_pages, total_records=total, items=items)

    async def count_jobs(self, flt: JobFilter) -> int:
        return int(await self._col.count_documents(self._query_doc(flt)))

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
        new_retries = job.retries + 1
        if error is None:
            patch: dict[str, Any] = {
                "status": JobStatus.SUCCESS,
                "finished_at": end_at.isoformat(),
                "updated_at": end_at.isoformat(),
                "retries": new_retries,
                "error": "",
                "result": result,
            }
        elif new_retries >= job.max_retry:
            patch = {
                "status": JobStatus.FAILURE,
                "finished_at": end_at.isoformat(),
                "updated_at": end_at.isoformat(),
                "retries": new_retries,
                "error": error,
            }
        else:
            patch = {
                "status": JobStatus.QUEUEING,
                "finished_at": None,
                "updated_at": end_at.isoformat(),
                "retries": new_retries,
                "error": error,
            }
        await self._col.update_one({"_id": job.id}, {"$set": patch})

    async def persist_trace_id(self, job_id: str, trace_id: str) -> None:
        await self._col.update_one(
            {"_id": job_id},
            {"$set": {"trace_id": trace_id, "updated_at": utcnow().isoformat()}},
        )

    async def retry_job(self, job_id: str) -> str | None:
        doc = await self._col.find_one({"_id": job_id}, {"task_name": 1})
        if doc is None:
            return None
        await self._col.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": JobStatus.QUEUEING,
                    "retries": 0,
                    "error": "",
                    "finished_at": None,
                    "updated_at": utcnow().isoformat(),
                }
            },
        )
        return str(doc.get("task_name", ""))

    async def retry_all(
        self,
        task_name: str,
        *,
        statuses: list[str] | None = None,
        search: str | None = None,
    ) -> int:
        query = self._query_doc(JobFilter(task_name=task_name, statuses=statuses, search=search))
        res = await self._col.update_many(
            query,
            {
                "$set": {
                    "status": JobStatus.QUEUEING,
                    "retries": 0,
                    "error": "",
                    "finished_at": None,
                    "updated_at": utcnow().isoformat(),
                }
            },
        )
        return int(res.modified_count)

    async def stop_job(self, job_id: str) -> str | None:
        doc = await self._col.find_one({"_id": job_id}, {"task_name": 1})
        if doc is None:
            return None
        await self._col.update_one(
            {"_id": job_id},
            {"$set": {"status": JobStatus.STOPPED, "updated_at": utcnow().isoformat()}},
        )
        return str(doc.get("task_name", ""))

    async def stop_all(self, task_name: str) -> int:
        res = await self._col.update_many(
            {"task_name": task_name, "status": {"$in": [JobStatus.QUEUEING, JobStatus.RETRYING]}},
            {"$set": {"status": JobStatus.STOPPED, "updated_at": utcnow().isoformat()}},
        )
        return int(res.modified_count)

    async def delete_job(self, job_id: str) -> str | None:
        doc = await self._col.find_one({"_id": job_id}, {"task_name": 1})
        if doc is None:
            return None
        await self._col.delete_one({"_id": job_id})
        return str(doc.get("task_name", ""))

    async def clean_jobs(
        self,
        task_name: str,
        *,
        statuses: list[str] | None = None,
        search: str | None = None,
    ) -> int:
        query = self._query_doc(JobFilter(task_name=task_name, statuses=statuses, search=search))
        res = await self._col.delete_many(query)
        return int(res.deleted_count)

    async def init_summaries(self, task_names: Iterable[str]) -> None:
        del task_names

    async def get_summaries(self, task_names: Iterable[str]) -> dict[str, TaskCounts]:
        names = list(task_names)
        result = {name: TaskCounts() for name in names}
        if not names:
            return result
        pipeline = [
            {"$match": {"task_name": {"$in": names}}},
            {"$group": {"_id": {"task_name": "$task_name", "status": "$status"}, "count": {"$sum": 1}}},
        ]
        async for doc in self._col.aggregate(pipeline):
            tn = doc["_id"]["task_name"]
            st = doc["_id"]["status"]
            cnt = int(doc["count"])
            counts = result.get(tn)
            if counts is None:
                continue
            if st == JobStatus.QUEUEING:
                counts.queueing = cnt
            elif st == JobStatus.RETRYING:
                counts.retrying = cnt
            elif st == JobStatus.SUCCESS:
                counts.success = cnt
            elif st == JobStatus.FAILURE:
                counts.failure = cnt
            elif st == JobStatus.STOPPED:
                counts.stopped = cnt
        return result
