"""Unit tests for standalone ``merapy-taskqueue`` package."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from merapy_taskqueue import (
    DashboardConfig,
    JobStatus,
    MemoryJobStore,
    TaskContext,
    TaskQueue,
    TaskQueueDashboard,
)
from merapy_taskqueue.dashboard import _safe_static_file


@pytest.mark.asyncio
async def test_enqueue_and_execute_success() -> None:
    store = MemoryJobStore()
    tq = TaskQueue(store=store, dashboard_enabled=False)
    seen: list[dict[str, object]] = []

    @tq.task("send_email")
    async def send_email(ctx: TaskContext) -> dict[str, bool]:
        seen.append(json.loads(ctx.arguments))
        return {"sent": True}

    job_id = await tq.enqueue("send_email", {"to": "user@example.com"}, max_retry=3)
    processed = await tq.tick()
    assert processed == 1
    assert seen == [{"to": "user@example.com"}]

    job = await store.get_job(job_id)
    assert job is not None
    assert job.status == JobStatus.SUCCESS
    assert job.retries == 1
    assert json.loads(job.result) == {"sent": True}


@pytest.mark.asyncio
async def test_retry_then_failure() -> None:
    store = MemoryJobStore()
    tq = TaskQueue(store=store, dashboard_enabled=False)

    @tq.task("flaky")
    async def flaky(ctx: TaskContext) -> None:
        del ctx
        raise RuntimeError("boom")

    job_id = await tq.enqueue("flaky", "{}", max_retry=2)

    await tq.tick()
    j1 = await store.get_job(job_id)
    assert j1 is not None
    assert j1.status == JobStatus.QUEUEING
    assert j1.retries == 1

    await tq.tick()
    j2 = await store.get_job(job_id)
    assert j2 is not None
    assert j2.status == JobStatus.FAILURE
    assert j2.retries == 2
    assert "boom" in j2.error


@pytest.mark.asyncio
async def test_dashboard_graphql_queries_and_mutations() -> None:
    store = MemoryJobStore()
    tq = TaskQueue(
        store=store,
        dashboard_enabled=False,
        service_name="billing-service",
        service_version="1.2.3",
    )

    @tq.task("invoice")
    async def invoice(ctx: TaskContext) -> None:
        del ctx

    app = TaskQueueDashboard(tq, config=tq.dashboard_config).build_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        add_res = await client.post(
            "/graphql",
            json={
                "query": """
                mutation {
                  add_job(param: { task_name: "invoice", max_retry: 3, args: "{\\"id\\": 42}" })
                }
                """
            },
        )
        assert add_res.status_code == 200
        job_id = add_res.json()["data"]["add_job"]
        assert job_id

        tasks_res = await client.post(
            "/graphql",
            json={
                "query": """
                query {
                  get_all_task { name total_jobs detail { queueing success } }
                  get_worker_stats { service_name service_version }
                }
                """
            },
        )
        assert tasks_res.status_code == 200
        body = tasks_res.json()["data"]
        assert body["get_all_task"][0]["name"] == "invoice"
        assert body["get_all_task"][0]["detail"]["queueing"] == 1
        assert body["get_worker_stats"]["service_name"] == "billing-service"

        stop_res = await client.post(
            "/graphql",
            json={"query": f'mutation {{ stop_job(job_id: "{job_id}") }}'},
        )
        assert stop_res.status_code == 200
        stopped = await store.get_job(job_id)
        assert stopped is not None
        assert stopped.status == JobStatus.STOPPED

        retry_res = await client.post(
            "/graphql",
            json={"query": f'mutation {{ retry_job(job_id: "{job_id}") }}'},
        )
        assert retry_res.status_code == 200
        retried = await store.get_job(job_id)
        assert retried is not None
        assert retried.status == JobStatus.QUEUEING

        del_res = await client.post(
            "/graphql",
            json={"query": f'mutation {{ delete_job(job_id: "{job_id}") }}'},
        )
        assert del_res.status_code == 200
        assert await store.get_job(job_id) is None


def test_safe_static_file_blocks_path_traversal(tmp_path: Path) -> None:
    root = tmp_path / "static"
    root.mkdir()
    (root / "index.html").write_text("ok", encoding="utf-8")
    secret = tmp_path / "secret.txt"
    secret.write_text("secret", encoding="utf-8")

    assert _safe_static_file(root.resolve(), "index.html") == (root / "index.html").resolve()
    assert _safe_static_file(root.resolve(), "../secret.txt") is None
    assert _safe_static_file(root.resolve(), "../../etc/passwd") is None
    assert _safe_static_file(root.resolve(), "\x00index.html") is None


def test_dashboard_config_defaults() -> None:
    cfg = DashboardConfig()
    assert cfg.port == 8080
    assert cfg.host == "0.0.0.0"
