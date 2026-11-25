# Merapy Step-by-Step Tutorial

This tutorial walks you from zero to a running microservice with REST, GraphQL, background jobs, and a real-time Task Queue dashboard — plus how to embed the standalone `merapy-taskqueue` package inside any existing Python app.

---

## Table of Contents

1. [Install the CLI](#1-install-the-cli)
2. [Scaffold Your First Service](#2-scaffold-your-first-service)
3. [Add Modules and Handlers](#3-add-modules-and-handlers)
4. [Configure the Database and Run](#4-configure-the-database-and-run)
5. [Enqueue and Monitor Jobs in the Live Dashboard](#5-enqueue-and-monitor-jobs-in-the-live-dashboard)
6. [Use `merapy-taskqueue` Standalone in Any Python Project](#6-use-merapy-taskqueue-standalone-in-any-python-project)
7. [Build Standalone Binaries and Releases](#7-build-standalone-binaries-and-releases)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Install the CLI

Choose whichever installation path fits your workflow:

### A. Standalone Binary (fastest — zero Python setup required)

Download the executable for your platform from [GitHub Releases](https://github.com/dimassantoso/merapy/releases):

```bash
# Example for macOS Apple Silicon
chmod +x merapy-macos-arm64
sudo mv merapy-macos-arm64 /usr/local/bin/merapy
merapy --version
```

### B. `pipx` or `uv` (Python 3.11+)

```bash
pipx install git+https://github.com/dimassantoso/merapy.git
# or:
uv tool install git+https://github.com/dimassantoso/merapy.git
```

---

## 2. Scaffold Your First Service

Run `merapy init` and follow the interactive prompts. In this tutorial we create `order-service` with an `order` module, REST + GraphQL APIs, a Task Queue worker, and PostgreSQL.

![Merapy CLI scaffolding walkthrough](assets/merapy-cli-demo.gif)

```bash
merapy init
```

Answer the prompts:

- **Service name:** `order-service`
- **Module names:** `order`
- **Server handlers:** `1,3` *(REST API + GraphQL)*
- **Worker handlers:** `6` *(Task Queue)*
- **Dependencies:** `2` *(SQL Database)*

Merapy scaffolds the complete clean-architecture project tree:

```text
order-service/
├── main.py                      # Startup migration guard + App(service).run()
├── Makefile                     # run, migration, migration-create, test, lint, proto
├── .env                         # Environment-driven server/worker toggles
├── merapy.json                  # Project metadata read by add-module / add-handler
├── alembic/                     # Auto-merges service models + TaskQueueBase tables
├── api/                         # GraphQL schemas, JSON schemas, Protobuf definitions
└── src/
    ├── configs/config.py        # DependencyBuilder wiring (DB, Redis, Brokers)
    ├── internal/
    │   ├── service.py           # ServiceFactory wiring modules & servers/workers
    │   └── modules/order/
    │       ├── module.py        # ModuleFactory
    │       ├── delivery/        # rest_handler.py, graphql_handler.py, task_queue_handler.py
    │       ├── usecase/         # Business logic
    │       ├── repository/      # SQLAlchemy 2.x async queries
    │       └── domain/          # Pydantic Request / Response / Filter DTOs
    └── pkg/shared/
        ├── domain/              # SQLAlchemy ORM models
        ├── repository/          # SharedRepository UOW singleton
        └── usecase/             # SharedUsecase UOW singleton (cross-module bridge)
```

---

## 3. Add Modules and Handlers

Whenever your service grows, let the CLI generate and wire new modules or transports automatically using `# @merapy:*` markers.

```bash
cd order-service

# Add a second domain module (automatically wired into service.py, shared UOW, and GraphQL)
merapy add-module payment

# Add a Cron scheduler handler to the existing order module
merapy add-handler order cron
```

You can also run `merapy` with no arguments inside the service directory to pick options interactively from the menu.

---

## 4. Configure the Database and Run

1. **Create a virtual environment and install project dependencies:**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

2. **Point `.env` at a dedicated PostgreSQL database** *(each service should use its own database to avoid Alembic version conflicts)*:

```bash
SQL_DSN_READ=postgresql+asyncpg://postgres:postgres@localhost:5432/order_service
SQL_DSN_WRITE=postgresql+asyncpg://postgres:postgres@localhost:5432/order_service
USE_REST=true
USE_GRAPHQL=true
USE_TASK_QUEUE_WORKER=true
TASK_QUEUE_DASHBOARD_PORT=8080
```

3. **Create the database, generate your first migration, apply it, and start:**

```bash
createdb order_service
make migration-create name=init
make migration
make run
```

> **Tip — Swap REST frameworks on the fly:**
> Run `REST_FRAMEWORK=litestar make run` to switch from FastAPI to Litestar without modifying a single route handler.

Test your generated REST endpoint:

```bash
curl http://localhost:8000/v1/order/
```

---

## 5. Enqueue and Monitor Jobs in the Live Dashboard

When `USE_TASK_QUEUE_WORKER=true`, your service automatically boots the embedded **Vite + Preact** Task Queue Dashboard on `http://localhost:8080`.

![Live Task Queue Dashboard walkthrough](assets/taskqueue-dashboard-demo.gif)

### Enqueueing a Job from a Usecase

```python
from merapy.codebase.app.task_queue_worker.client import TaskQueueClient
from merapy.codebase.factory.dependency import get_dependency

client = TaskQueueClient(get_dependency().sql_db().session_factory())
job_id = await client.enqueue(
    "order-task",
    args={"order_id": 1042, "action": "send_receipt"},
    max_retry=3,
)
```

### What You Can Do in the Dashboard

- **Step 1–2 (Overview):** Watch live status cards (`Total`, `Queued`, `Running`, `Success`, `Failure`, `Stopped`), deployment metadata, process memory/CPU stats, and every registered task update in real time over WebSocket subscriptions.
- **Step 3 (Task Jobs `/task`):** Click any task to filter by status, search job arguments, add manual test jobs, or bulk retry/stop/clear jobs.
- **Step 4–5 (Job Inspector `/job`):** Click any job ID to view formatted JSON arguments, result payloads, error messages, OpenTelemetry Trace IDs, and trigger one-click **Retry**, **Stop**, or **Delete**.

### Showing Deployment Info in the Dashboard

Pass optional build environment variables in CI/CD or Docker:

```bash
SERVICE_NAME=order-service
APP_VERSION=1.4.2
BUILD_NUMBER=142
GIT_COMMIT=1793183
BUILD_DATE=2026-11-25T18:00:00Z
```

---

## 6. Use `merapy-taskqueue` Standalone in Any Python Project

Want the background job queue and live dashboard in a plain FastAPI, Starlette, Django, or `asyncio` project **without** adopting the full `merapy` microservice framework? Install `merapy-taskqueue` on its own.

![Standalone merapy-taskqueue tutorial](assets/standalone-taskqueue-demo.gif)

### Install

```bash
# Minimal (in-memory store + embedded Preact dashboard)
pip install "merapy-taskqueue @ git+https://github.com/dimassantoso/merapy-taskqueue.git"

# With SQL, MongoDB, Redis, or all optional extras
pip install "merapy-taskqueue[sql] @ git+https://github.com/dimassantoso/merapy-taskqueue.git"
pip install "merapy-taskqueue[mongo] @ git+https://github.com/dimassantoso/merapy-taskqueue.git"
pip install "merapy-taskqueue[redis] @ git+https://github.com/dimassantoso/merapy-taskqueue.git"
pip install "merapy-taskqueue[all] @ git+https://github.com/dimassantoso/merapy-taskqueue.git"
```

### Minimal Runnable Script (`app.py`)

```python
import asyncio
import json
from merapy_taskqueue import MemoryJobStore, TaskContext, TaskQueue

tq = TaskQueue(
    store=MemoryJobStore(),
    dashboard_port=8080,
    service_name="billing-app",
    service_version="1.0.0",
)

@tq.task("send_email")
async def send_email(ctx: TaskContext) -> dict[str, object]:
    payload = json.loads(ctx.arguments)
    return {"delivered": True, "to": payload["to"]}

async def main() -> None:
    await tq.enqueue("send_email", {"to": "alice@example.com"}, max_retry=3)
    await tq.serve()  # runs worker loop + dashboard at http://localhost:8080

asyncio.run(main())
```

### Choose Your Storage Backend

```python
# 1. PostgreSQL / MySQL / SQLite (SQLAlchemy 2.x async)
from merapy_taskqueue import SQLJobStore, TaskQueueBase
store = SQLJobStore(async_session_factory)

# 2. MongoDB (Motor)
from merapy_taskqueue import MongoJobStore
store = MongoJobStore(motor_database)

# 3. Redis (redis.asyncio)
from merapy_taskqueue import RedisJobStore
store = RedisJobStore(async_redis_client)
```

### Mount the Dashboard Inside an Existing FastAPI App

```python
from fastapi import FastAPI
from merapy_taskqueue import MemoryJobStore, TaskQueue

app = FastAPI()
tq = TaskQueue(store=MemoryJobStore(), dashboard_enabled=False)

@tq.task("resize_image")
async def resize_image(ctx):
    ...

app.mount("/tasks", tq.dashboard_app())
```

---

## 7. Build Standalone Binaries and Releases

From the `merapy` repository root:

```bash
# Rebuild the Vite + Preact dashboard UI and embed into both packages
make ui-build

# Build standalone CLI binary + Python wheels/sdists + SHA256SUMS into release/
make release
```

To publish Linux, macOS, and Windows binaries automatically on GitHub Releases:

```bash
git tag -a v0.2.0 -m "Release v0.2.0"
git push origin v0.2.0
```

---

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `alembic Can't locate revision` | Each service needs its own DB. Run `alembic stamp base` and re-run `make migration`. |
| Task queue tables missing on startup | Run `make migration-create name=add_task_queue_tables && make migration`. |
| Memory metrics show `0.0` in dashboard | Install `psutil` in your service virtual environment: `.venv/bin/pip install psutil`. |
| Dashboard served on custom port or reverse proxy | Handled automatically — the Vite + Preact UI auto-detects same-origin `/graphql` and WebSocket (`ws://` / `wss://`). |
