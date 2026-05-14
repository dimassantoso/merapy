# AGENTS.md — kapynis workspace context

> Read this first. Full reference is in `CLAUDE.md`.

## What this is

**kapynis** — Python microservice framework porting Go [candi](https://github.com/golangid/candi).
GitHub: https://github.com/dimassantoso/merapy

## Key paths

| What | Where |
|------|-------|
| Framework source | `/Users/dimas/Documents/Project/personal/kapynis/src/kapynis/` |
| CLI templates | `src/kapynis/cli/templates/` |
| Task queue dashboard (Python backend) | `src/kapynis/codebase/app/task_queue_worker/dashboard.py` |
| Embedded dashboard static files | `src/kapynis/codebase/app/task_queue_worker/dashboard_static/` |
| Dashboard UI repo | `/Users/dimas/Documents/Project/personal/merapy-taskqueue-dashboard/` |
| candi Go source (reference) | `/Users/dimas/Documents/Project/OpenSource/candi/` |
| candi dashboard reference | `/Users/dimas/Documents/Project/OpenSource/task-queue-worker-dashboard/` |
| Example services | `/Users/dimas/Documents/Project/personal/{user,product}-service/` |

## Dev commands

```bash
# In /Users/dimas/Documents/Project/personal/kapynis
.venv/bin/pip install -e ".[dev]"   # install editable
.venv/bin/pytest tests/unit -v      # run tests
.venv/bin/ruff check src tests      # lint
.venv/bin/mypy src                  # type-check

# CLI
merapy init          # scaffold new service
merapy add-module    # add module to service
merapy add-handler   # add delivery handler

# Dashboard (rebuild + embed into kapynis)
cd /Users/dimas/Documents/Project/personal/merapy-taskqueue-dashboard
make embed KAPYNIS_DIR=/Users/dimas/Documents/Project/personal/kapynis
```

## Generated service commands

```bash
make run                          # .venv/bin/python main.py
make migration-create name=init   # alembic revision --autogenerate
make migration                    # alembic upgrade head
make proto                        # generate gRPC stubs (if USE_GRPC=true)
```

## Critical rules

1. **Always use `.venv/bin/python`** — never system `python`. Services use `.venv/bin/python` via Makefile.
2. **Each service needs its own database** — shared DB causes `alembic_version` conflicts.
3. **Task queue tables** use `TaskQueueBase` (separate from service `Base`) — must merge metadata in `alembic/env.py`.
4. **`TaskBase` is now `TaskQueueBase`** — old name causes ImportError.
5. **Strawberry auto-camelCase** — task queue dashboard schema uses `StrawberryConfig(auto_camel_case=False)` to match candi's snake_case field names.
6. **Dashboard embed** — after changing `merapy-taskqueue-dashboard`, always run `make embed` to update `dashboard_static/`.
7. **Broker connect** — Kafka/RabbitMQ `start()` is wrapped with `asyncio.wait_for(timeout=10)` — if broker is down, service logs warning and continues.

## Architecture in one diagram

```
merapy init → generates service/
  ├── main.py              ← check_pending_migrations() then App(service).run()
  ├── src/internal/
  │   ├── service.py       ← ServiceFactory: modules + apps
  │   └── modules/<name>/
  │       ├── module.py    ← ModuleFactory (conditional on use_X flags)
  │       ├── delivery/    ← rest/grpc/graphql/kafka/cron/redis/rabbitmq/postgres/task_queue
  │       ├── usecase/     ← business logic
  │       └── repository/  ← SQL/Mongo data access
  └── src/pkg/shared/
      ├── repository/      ← SharedRepository UOW (SQL + Mongo)
      └── usecase/         ← SharedUsecase UOW (cross-module bridge)
```

## Task queue dashboard

- **Port**: `TASK_QUEUE_DASHBOARD_PORT` (default 8080)
- **Served by**: `dashboard.py` — FastAPI + strawberry GraphQL + embedded Next.js static files
- **GraphQL schema** (snake_case, `auto_camel_case=False`):
  - Queries: `get_all_job`, `get_count_job`, `get_all_task`
  - Mutations: `add_job`, `retry_job`, `stop_job`, `stop_all_job`, `retry_all_job`, `delete_job`, `clean_job`
  - Subscriptions: `listen_task_dashboard`, `listen_all_job` (push every 2s)
- **Tables**: `task_queue_worker_jobs`, `task_queue_worker_job_summaries`, `task_queue_worker_job_histories`, `task_queue_worker_configurations`
- **Status values**: `QUEUEING`, `RETRYING`, `SUCCESS`, `FAILURE`, `STOPPED`
- **Button semantics**: Retry = FAILURE/STOPPED only; Stop = QUEUEING/RETRYING only; Delete = always

## Common pitfalls

| Problem | Fix |
|---------|-----|
| `alembic Can't locate revision` | `alembic stamp base` — stale row from another service |
| `TaskBase` ImportError | Use `TaskQueueBase` (renamed) |
| Dashboard not reachable | Check service uses `.venv/bin/python`, not system Python |
| Aggregate numbers wrong | Compute from `detail.queueing + detail.retrying + ...`, not `total_jobs` field |
| GraphQL field not found | Dashboard uses snake_case; check `auto_camel_case=False` is set |
| `options` unresolved in Litestar | Use `HTTPRouteHandler(path, http_method="OPTIONS")` |
| Strawberry `Unexpected type` | Wrap Pydantic model with `@strawberry.experimental.pydantic.type(model=..., all_fields=True)` |
| Kafka/RabbitMQ crashes on start | Broker connect has 10s timeout + graceful fallback — check broker is running |

## Marker system (code generation)

`# @kapynis:<name>` comments in generated files. `inject(path, marker, code)` appends after marker (idempotent).

Key markers: `repositoryImport/Method/Field/Constructor/Implementation`, `usecaseImport/Method/Field/Common/Implementation`, `moduleImport/Init`, `queryRoot/mutationRoot/subscriptionRoot`

Also: `repositoryMongoImport/Method/Field/Constructor/Implementation` for MongoDB repos.
