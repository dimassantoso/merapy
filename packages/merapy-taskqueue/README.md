# merapy-taskqueue

Standalone async Python task queue with pluggable storage backends (**In-Memory**, **SQLAlchemy**, **MongoDB**, **Redis**) and a built-in real-time GraphQL dashboard powered by **Vite + Preact + Tailwind CSS v4**.

Use it in **any** Python project (FastAPI, Starlette, Django, plain `asyncio` scripts) without installing the full `merapy` microservice framework.

## Install

```bash
pip install merapy-taskqueue          # core + in-memory store + embedded dashboard
pip install "merapy-taskqueue[sql]"   # + SQLAlchemy 2.x async store
pip install "merapy-taskqueue[mongo]" # + MongoDB (Motor) store
pip install "merapy-taskqueue[redis]" # + Redis async store
pip install "merapy-taskqueue[all]"   # everything + psutil metrics
```

## Quickstart (any Python app)

```python
import asyncio
from merapy_taskqueue import MemoryJobStore, TaskContext, TaskQueue

tq = TaskQueue(store=MemoryJobStore(), dashboard_port=8080, service_name="billing-app")

@tq.task("send_email")
async def send_email(ctx: TaskContext) -> None:
    print("Processing job:", ctx.job_id, ctx.arguments)

async def main() -> None:
    await tq.enqueue("send_email", {"to": "alice@example.com"})
    await tq.serve()  # worker loop + dashboard at http://localhost:8080

asyncio.run(main())
```

### Mount inside an existing FastAPI app

```python
from fastapi import FastAPI
from merapy_taskqueue import MemoryJobStore, TaskQueue

app = FastAPI()
tq = TaskQueue(store=MemoryJobStore())

@tq.task("resize_image")
async def resize_image(ctx):
    ...

app.mount("/tasks", tq.dashboard_app())
```

## Rebuilding the Dashboard UI

```bash
cd ui
npm install
npm run build   # compiles directly into src/merapy_taskqueue/dashboard_static/
```
