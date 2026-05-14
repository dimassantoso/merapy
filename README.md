# merapy

**merapy** is a Python clean-architecture microservice framework. It gives you a structured, async-first foundation for building production services — with an interactive CLI that scaffolds projects, modules, and delivery handlers so you spend time on business logic, not boilerplate.

Targets **Python 3.11+**. Async-first across every layer.

---

## What you get

- **One service, many transports.** REST + gRPC + GraphQL + 6 worker types (Kafka, RabbitMQ, Redis pub/sub, Cron, Postgres LISTEN, persistent Task Queue) — all wired into a single `asyncio.gather` orchestrator with graceful shutdown.
- **Pluggable REST adapter.** FastAPI by default. Litestar via `REST_FRAMEWORK=litestar`. Module handlers depend only on the abstract `RESTRouter` Protocol — same code works under both.
- **Clean architecture enforced.** `delivery → usecase → repository → DB` separation baked into every generated module. Cross-module calls route through a singleton bridge, eliminating circular imports.
- **Thread-safe singletons.** Dependency container, shared repository, and shared usecase are each initialised once at boot via `threading.Lock` — idempotent and safe.
- **Code-gen markers.** `# @merapy:*` comments in generated files let `merapy add-module` extend shared usecase / repository / service files automatically, without manual edits.
- **SQLAlchemy 2.x async + Alembic + Pydantic v2 + structlog + OpenTelemetry** out of the box.
- **Task Queue dashboard.** Built-in GraphQL API + embedded Next.js UI served on `TASK_QUEUE_DASHBOARD_PORT` (default 8080). Open `http://localhost:8080` after `make run`.

---

## Repos

| Repo | Purpose |
|------|---------|
| [`merapy`](https://github.com/dimassantoso/merapy) | The framework |
| [`merapy-taskqueue-dashboard`](https://github.com/dimassantoso/merapy-taskqueue-dashboard) | Task queue dashboard UI (Next.js, embedded into merapy) |
| [`merapy-plugin`](https://github.com/dimassantoso/merapy-plugin) | Optional adapters (brokers, storage, REST engines) |

---

## Install

Requires **Python 3.11+** (3.12 is the development reference).

### As an end user — just want the CLI

```bash
# pipx (recommended — isolated, global CLI)
pipx install merapy                                          # once on PyPI
pipx install git+https://github.com/dimassantoso/merapy.git  # from GitHub

# uv (faster alternative)
uv tool install git+https://github.com/dimassantoso/merapy.git
```

### As a contributor — editable clone

```bash
git clone https://github.com/dimassantoso/merapy.git
cd merapy
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

---

## Quickstart

```bash
# 1. Scaffold interactively
merapy init
```

```
What do you want?
1) Init service
2) Add module(s) in service
3) Add delivery handler(s) in module
>> 1

Please input service name
>> my-service

Please input new module names (if more than one, separated by comma)
>> product

Please select server handlers (separated by comma, enter for skip)
1) REST API  2) GRPC  3) GraphQL
>> 1,3

Please select worker handlers (separated by comma, enter to skip)
1) Kafka  2) Cron Scheduler  3) Redis Subscriber
4) RabbitMQ  5) Postgres Listener  6) Task Queue
>> 6

Please select dependencies (separated by comma, enter to skip)
1) Redis  2) SQL Database  3) Mongo Database
>> 2

✓ service 'my-service' scaffolded at ./my-service
```

```bash
# 2. Enter the service and install dependencies
cd my-service
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 3. Configure .env (set your actual DB DSN)
# SQL_DSN_WRITE=postgresql+asyncpg://postgres:postgres@localhost:5432/my_service

# 4. Create the database
createdb my_service

# 5. Run migrations
make migration-create name=init
make migration

# 6. Start the service
make run
```

REST API: `http://localhost:8000/v1/product/`
GraphQL: `http://localhost:8100/graphql`
Task Queue Dashboard: `http://localhost:8080` *(if USE_TASK_QUEUE_WORKER=true)*

---

## CLI reference

Running `merapy` with no arguments opens the interactive menu.

| Command | What it does |
|---------|-------------|
| `merapy init` | Wizard: service name → modules → server handlers → worker handlers → dependencies. Scaffolds a complete service. |
| `merapy add-module <name>` | Generates `src/internal/modules/<name>/` (module + domain + usecase + repository + delivery handlers) and injects `# @merapy:*` markers into shared UOW files. |
| `merapy add-handler <module> <type>` | Adds a delivery handler (`rest`/`grpc`/`graphql`/`kafka`/`cron`/`redis`/`rabbitmq`/`postgres`/`task_queue`) to an existing module. |

---

## Makefile targets

| Target | What it does |
|--------|-------------|
| `make run` | Start the service (`python main.py`) |
| `make migration-create name=X` | Generate alembic migration file |
| `make migration` | Apply pending migrations (`alembic upgrade head`) |
| `make migration-down` | Roll back last migration |
| `make test` | Run pytest |
| `make lint` | Ruff lint |
| `make typecheck` | mypy |
| `make proto` | Generate gRPC stubs from `api/proto/*.proto` *(if USE_GRPC=true)* |

---

## Configuration

Every boot decision is **env-driven**. The `.env` generated by `merapy init` contains only the toggles relevant to your selections:

```bash
SERVICE_NAME=my-service
ENVIRONMENT=development
DEBUG_MODE=true
LOAD_CONFIG_TIMEOUT=30s

# Server handlers
USE_REST=true
USE_GRPC=false
USE_GRAPHQL=true
HTTP_PORT=8000
HTTP_ROOT_PATH=/
REST_FRAMEWORK=fastapi   # or: litestar
GRPC_PORT=8002

# Worker handlers
USE_KAFKA_CONSUMER=false
USE_CRON_SCHEDULER=false
USE_REDIS_SUBSCRIBER=false
USE_RABBITMQ_WORKER=false
USE_POSTGRES_LISTENER=false
USE_TASK_QUEUE_WORKER=true
TASK_QUEUE_DASHBOARD_PORT=8080

# Datastores
SQL_DSN_READ=postgresql+asyncpg://postgres:postgres@localhost:5432/my_service
SQL_DSN_WRITE=postgresql+asyncpg://postgres:postgres@localhost:5432/my_service
REDIS_DSN_READ=redis://localhost:6379/0
REDIS_DSN_WRITE=redis://localhost:6379/0

# Brokers (only included when selected)
KAFKA_BROKERS=localhost:9092
KAFKA_CLIENT_ID=my_service
KAFKA_CONSUMER_GROUP=my_service
RABBITMQ_BROKER=amqp://guest:guest@localhost:5672/
RABBITMQ_EXCHANGE_NAME=delayed

CORS_ALLOW_ORIGINS=["*"]
MAX_WORKERS=10

# Build / deployment info (optional — displayed in task queue dashboard)
APP_VERSION=1.0.0
BUILD_NUMBER=42
GIT_COMMIT=abc1234
BUILD_DATE=2026-05-14T10:30:00Z
```

---

## Generated service layout

```
my-service/
├── api/
│   ├── graphql/
│   │   ├── _schema.graphql      ← root schema with @merapy:queryRoot markers
│   │   ├── _common.graphql      ← shared types (FilterListInputResolver, MetaResolver)
│   │   └── <module>.graphql     ← per-module GraphQL types
│   ├── jsonschema/
│   │   └── <module>/
│   │       ├── get_all.json
│   │       └── save.json
│   └── proto/
│       └── <module>/
│           └── <module>.proto   ← gRPC service definition
├── alembic/
│   └── env.py                   ← sys.path fix + load_dotenv + merged metadata
├── alembic.ini
├── main.py                      ← entry point (includes migration guard)
├── pyproject.toml
├── Makefile
├── .env
├── merapy.json                  ← scaffolding config
└── src/
    ├── internal/
    │   ├── service.py           ← ServiceFactory wiring
    │   └── modules/<name>/
    │       ├── module.py        ← ModuleFactory (conditional handler wiring)
    │       ├── domain/          ← Pydantic DTOs (Filter/Request/Response)
    │       ├── delivery/
    │       │   ├── rest_handler.py
    │       │   ├── grpc_handler.py
    │       │   ├── graphql_handler.py
    │       │   ├── kafka_handler.py
    │       │   ├── cron_handler.py
    │       │   ├── redis_handler.py
    │       │   ├── rabbitmq_handler.py
    │       │   ├── postgres_handler.py
    │       │   └── task_queue_handler.py
    │       ├── usecase/         ← Protocol + _Impl (get_all/get_detail/create/update/delete)
    │       └── repository/      ← Protocol + RepoSQL (SQLAlchemy 2.x async)
    ├── pkg/
    │   └── shared/
    │       ├── domain/          ← SQLAlchemy DeclarativeBase + ORM models
    │       ├── repository/      ← SharedRepository UOW singleton
    │       └── usecase/         ← SharedUsecase UOW singleton
    └── configs/
        └── config.py            ← load_service_configs (DB, brokers, deps)
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  main.py                                                         │
│    └─ App(service).run()      ← asyncio.gather + SIGINT/SIGTERM  │
│         ↑                                                        │
│  Service (your generated factory)                                │
│    ├─ config()                                                   │
│    ├─ dependency()            ← module-level Dependency singleton│
│    ├─ modules()               ← list of ModuleFactory            │
│    └─ applications()          ← list of AppServerFactory         │
└──────────────────────────────────────────────────────────────────┘

Per-module clean-architecture flow:

    REST/gRPC/GraphQL/Worker handler ──► Usecase ──► Repository ──► DB
                                            │
                                            └─► shared_usecase (cross-module bridge)
```

| Layer | Location | Responsibility |
|-------|----------|---------------|
| **Delivery** | `src/internal/modules/<m>/delivery/` | HTTP / gRPC / GraphQL / worker glue |
| **Usecase** | `src/internal/modules/<m>/usecase/` | Business logic |
| **Repository** | `src/internal/modules/<m>/repository/` | Data access via SQLAlchemy async |
| **Domain** | `src/internal/modules/<m>/domain/` | Pydantic DTOs |
| **Shared DB models** | `src/pkg/shared/domain/` | SQLAlchemy models registered with Alembic |
| **Shared UOW** | `src/pkg/shared/{repository,usecase}/` | Singleton aggregators extended by `add-module` |

---

## Task Queue Dashboard

When `USE_TASK_QUEUE_WORKER=true`, the worker automatically serves a dashboard on `TASK_QUEUE_DASHBOARD_PORT` (default **8080**):

- `http://localhost:8080/` — dashboard UI (embedded Next.js static build)
- `http://localhost:8080/graphql` — GraphQL API + WebSocket subscriptions

**Features:**
- View all registered tasks with live job counts per status
- Drill into a task to see individual jobs (paginated, filterable)
- View full job detail: arguments, result, error, trace ID, timestamps
- Retry failed/stopped jobs (single or bulk)
- Stop running/queued jobs — button disabled when nothing is stoppable
- Delete jobs permanently
- Bulk clean by task + status
- Add new jobs manually
- Real-time updates via GraphQL subscriptions (push every 2s, immediate on mutations)

**Service info panel** — always visible, shows two sections:

*Deployment* — set these env vars in your CI/CD pipeline:
```bash
SERVICE_NAME=user-service       # displayed as "USER SERVICE" in navbar
APP_VERSION=1.4.2
BUILD_NUMBER=142                # e.g. ${{ github.run_number }}
GIT_COMMIT=a3f9c12...           # e.g. ${{ github.sha }}
BUILD_DATE=2026-05-14T10:30:00Z # e.g. ${{ github.event.head_commit.timestamp }}
```

*Runtime* — live process metrics (install `psutil` for full data):
```bash
.venv/bin/pip install psutil
```
Memory auto-scales: B / KB / MB / GB / TB.

The dashboard UI is maintained in [`merapy-taskqueue-dashboard`](https://github.com/dimassantoso/merapy-taskqueue-dashboard) and embedded into the merapy package via `make embed`.

---

## Swap the REST engine

```bash
REST_FRAMEWORK=fastapi python main.py   # default
REST_FRAMEWORK=litestar python main.py  # alternative
```

Module handlers only depend on the abstract `RESTRouter` Protocol — same code works under both.

---

## Migration guard

`main.py` calls `check_pending_migrations(cfg)` at startup. If tables are missing it:
1. Auto-generates an alembic revision file
2. Prints clear instructions
3. Exits with code 1

```
✗ Database schema is out of date.
  Missing tables: 'product'

  Generating .../alembic/versions/20260513_add_product.py

✓ Migration file created. Run:

    make migration

Then restart with:

    make run
```

---

## Development

```bash
make test       # pytest tests/unit
make lint       # ruff check src tests
make typecheck  # mypy src
```

CLI smoke test after changes:

```bash
merapy init    # answer the wizard, name it demo-svc
cd demo-svc
python -m py_compile src/internal/service.py
python -m py_compile src/internal/modules/*/usecase/usecase.py
```

---

## License

See [`LICENSE`](LICENSE).
