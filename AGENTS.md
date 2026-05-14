# AGENTS.md — merapy workspace context

> Read this first. Full reference is in `CLAUDE.md`.

## What this is

**merapy** — Python clean-architecture microservice framework.
GitHub: https://github.com/dimassantoso/merapy

## Key paths

| What | Where |
|------|-------|
| Framework source | `src/merapy/` |
| CLI templates | `src/merapy/cli/templates/` |
| Task queue dashboard (Python backend) | `src/merapy/codebase/app/task_queue_worker/dashboard.py` |
| Embedded dashboard static files | `src/merapy/codebase/app/task_queue_worker/dashboard_static/` |
| Env config | `src/merapy/config/env.py` |
| Dashboard UI repo | `/Users/dimas/Documents/Project/personal/merapy-taskqueue-dashboard/` |
| Example services | `/Users/dimas/Documents/Project/personal/{user,product}-service/` |

## Dev commands

```bash
# In /Users/dimas/Documents/Project/personal/merapy
.venv/bin/pip install -e ".[dev]"   # install editable
.venv/bin/pytest tests/unit -v      # run tests
.venv/bin/ruff check src tests      # lint
.venv/bin/mypy src                  # type-check

# CLI
merapy init          # scaffold new service
merapy add-module    # add module to service
merapy add-handler   # add delivery handler

# Dashboard (rebuild + embed into merapy)
cd /Users/dimas/Documents/Project/personal/merapy-taskqueue-dashboard
make embed MERAPY_DIR=/Users/dimas/Documents/Project/personal/merapy
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
5. **Strawberry auto-camelCase** — task queue dashboard schema uses `StrawberryConfig(auto_camel_case=False)` to keep snake_case field names.
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
  - Queries: `get_all_job`, `get_count_job`, `get_all_task`, `get_worker_stats`
  - Mutations: `add_job`, `retry_job`, `stop_job`, `stop_all_job`, `retry_all_job`, `delete_job`, `clean_job`
  - Subscriptions: `listen_task_dashboard`, `listen_all_job` (push every 2s)
- **`listen_task_dashboard` response** includes `stats: WorkerStatsResolver` with:
  - `memory_rss_mb`, `memory_vms_mb`, `memory_percent`, `cpu_percent`
  - `merapy_version`, `service_name`, `service_version`
  - `build_number`, `git_commit`, `build_date`
- **Tables**: `task_queue_worker_jobs`, `task_queue_worker_job_summaries`, `task_queue_worker_job_histories`, `task_queue_worker_configurations`
- **Status values**: `QUEUEING`, `RETRYING`, `SUCCESS`, `FAILURE`, `STOPPED`
- **Button semantics**: Retry = FAILURE/STOPPED only; Stop = QUEUEING/RETRYING only (disabled when none active); Delete = always

## Build / deployment env vars (all optional)

| Env var | Field | Default | Purpose |
|---------|-------|---------|---------|
| `SERVICE_NAME` | `service_name` | `merapy-service` | Displayed in dashboard navbar |
| `APP_VERSION` | `app_version` | `dev` | Semantic version / release tag |
| `BUILD_NUMBER` | `build_number` | `""` | CI build number (GitHub Actions run, Jenkins ID) |
| `GIT_COMMIT` | `git_commit` | `""` | Git commit SHA baked in at build time |
| `BUILD_DATE` | `build_date` | `""` | ISO-8601 build timestamp |

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
| Memory shows `0.0` | Install `psutil` in service venv: `.venv/bin/pip install psutil` |

## Marker system (code generation)

`# @merapy:<name>` comments in generated files. `inject(path, marker, code)` appends after marker (idempotent).

Key markers: `repositoryImport/Method/Field/Constructor/Implementation`, `usecaseImport/Method/Field/Common/Implementation`, `moduleImport/Init`, `queryRoot/mutationRoot/subscriptionRoot`

Also: `repositoryMongoImport/Method/Field/Constructor/Implementation` for MongoDB repos.

## merapy-plugin

Repo: `/Users/dimas/Documents/Project/personal/merapy-plugin/`

All 11 plugins are implemented. Each is an independent Python package.

| Directory | PyPI name | Worker/Server type | Status |
|---|---|---|---|
| `aws-sqs-sns/` | `merapy-aws-sqs-sns` | `Worker.AMAZONSQS` | ✅ |
| `gcp-pubsub/` | `merapy-gcp-pubsub` | `Worker.GCP_PUBSUB` | ✅ |
| `stomp-broker/` | `merapy-stomp-broker` | `Worker.STOMP` | ✅ |
| `p2p/` | `merapy-p2p` | `Server.P2P_TCP` / `Server.P2P_UDP` | ✅ |
| `sanic-rest/` | `merapy-sanic-rest` | REST adapter | ✅ |
| `blacksheep-rest/` | `merapy-blacksheep-rest` | REST adapter | ✅ |
| `oracledb/` | `merapy-oracledb` | `SQLDatabase` Protocol | ✅ |
| `arangodb/` | `merapy-arangodb` | `extended("arangodb")` | ✅ |
| `circuit-breaker/` | `merapy-circuit-breaker` | standalone decorator | ✅ |
| `tracer-otlp/` | `merapy-tracer-otlp` | OTel exporter | ✅ |
| `task-queue-admin/` | `merapy-task-queue-admin` | Mongo/Redis job stores | ✅ |

**Plugin worker types** are first-class enum values in `merapy.codebase.types`:
- `Worker.AMAZONSQS = "amazonsqs_broker"`
- `Worker.GCP_PUBSUB = "gcp_pubsub"`
- `Worker.STOMP = "stomp_broker"`
- `Server.P2P_TCP = "p2p_tcp"`
- `Server.P2P_UDP = "p2p_udp"`

**Common pitfalls for plugins:**
- Always use `Worker.AMAZONSQS` etc. — never `Worker("amazonsqs_broker")` raw cast (raises `ValueError`)
- `SQSPublisher` reuses a single aioboto3 client per `serve()` lifetime for performance
- `BlackSheepRouteWrapper` stores `_RouteSpec` tuples and flushes via `app.router.add_route()` — never iterate the router object
- `SanicRouteWrapper` uses `Blueprint.group()` for nesting — never call `.blueprint()` on a Blueprint
- `OracleSQLDatabase` uses `async_sessionmaker(engine)` — not `sessionmaker(bind=engine)` (SA 1.x style)
- `TaskQueueAdminWorker` sets `self._session_factory = None` so the dashboard shows task names without DB queries
