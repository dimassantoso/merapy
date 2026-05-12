# kapynis

Python clean-architecture microservice framework — a Pythonic port of [candi](https://github.com/golangid/candi) (Go).

`kapynis` gives you the same factory + singleton + clean-architecture shape candi gives Go services, with an interactive CLI that scaffolds projects and modules the same way `candi -init` / `candi -add-module` does. It targets Python 3.11+ and is async-first across every layer.

---

## What you get

- **One service binary, many transports.** REST + gRPC + GraphQL + 6 worker types (Kafka, RabbitMQ, Redis pub/sub, Cron, Postgres LISTEN, persistent TaskQueue) — all wired into a single `asyncio.gather` orchestrator with graceful shutdown.
- **REST adapter is pluggable.** FastAPI by default. Litestar via `REST_FRAMEWORK=litestar`. Module handlers see only the `RESTRouter` Protocol — same code works under both.
- **Clean architecture by default.** `delivery → usecase → repository → DB` separation enforced by the module template; cross-module calls route through a singleton bridge so there's never a circular import.
- **Singletons that mirror candi's `sync.Once`** — idempotent, thread-safe, set once at boot.
- **Code-gen markers** (`# @kapynis:*`) so `kapynis add-module` extends the shared usecase / repository / service files without you editing them.
- **SQLAlchemy 2.x async + Alembic migrations + Pydantic v2 + structlog + OpenTelemetry** out of the box.

---

## Install

Requires **Python 3.11+** (3.12 is the development reference).

### As an end user — just want the CLI

**Recommended: [`pipx`](https://pipx.pypa.io/)** — installs the CLI into its own isolated venv, drops `kapynis` on your PATH globally. The Python equivalent of `go install`.

```bash
# One-time setup
brew install pipx && pipx ensurepath

# Install kapynis
pipx install kapynis                                       # once published to PyPI
pipx install git+https://github.com/santosodb/kapynis.git  # before PyPI — direct from GitHub
```

Or with [`uv`](https://docs.astral.sh/uv/) (faster, modern alternative):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install kapynis                                       # once on PyPI
uv tool install git+https://github.com/santosodb/kapynis.git  # before PyPI
```

Now `kapynis` works anywhere on the system.

Plain `pip install kapynis` also works but pollutes the active environment — prefer pipx / uv for CLI tools.

### As a contributor — editable clone for development

```bash
git clone https://github.com/santosodb/kapynis.git
cd kapynis
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

`kapynis` is now on your PATH inside the venv; edits to `src/kapynis/` take effect immediately.

---

## Quickstart — scaffold and run a service

```bash
# 1. Scaffold interactively — wizard prompts for name, modules, handlers, deps
kapynis init
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
>> expense

Please select server handlers (separated by comma, enter for skip)
1) REST API
2) GRPC
3) GraphQL
>> 1

Please select worker handlers (separated by comma, enter to skip)
1) Kafka
2) Cron Scheduler
3) Redis Subscriber
4) RabbitMQ
5) Postgres Listener
6) Task Queue
>>

Please select dependencies (separated by comma, enter to skip)
1) Redis
2) SQL Database
3) Mongo Database
>> 2

✓ service 'my-service' scaffolded at ./my-service
```

```bash
# 2. Install the service's dependencies
cd my-service
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# 3. Add more modules any time
.venv/bin/kapynis add-module

# 4. Configure datastores (edit .env)
# 5. Run migrations
.venv/bin/alembic revision --autogenerate -m "init"
.venv/bin/alembic upgrade head

# 6. Boot the service
.venv/bin/python main.py
```

By default the service binds REST on `http://localhost:8000/`. Try:

```bash
curl http://localhost:8000/v1/expense/
```

Expected envelope:

```json
{
  "success": true,
  "code": 200,
  "message": "success",
  "meta": { "page": 1, "limit": 10, "totalRecords": 0, "totalPages": 0 },
  "data": []
}
```

---

## CLI reference

Running `kapynis` with no arguments opens the interactive menu — identical to candi's UX.
All three commands can also be invoked directly:

| Command | What it does |
|---|---|
| `kapynis init` | Interactive wizard: service name → modules → server handlers → worker handlers → dependencies. Scaffolds a complete service directory. |
| `kapynis add-module` | Generates `src/internal/modules/<name>/` (module + domain + usecase + repository + REST handler + SQLAlchemy model) and injects `# @kapynis:*` markers into the shared usecase / repository / service files. |
| `kapynis add-handler` | Adds a delivery handler (`rest` / `cron` / `kafka` / …) to an existing module. |

The CLI uses Click + Jinja2 templates bundled inside the package at `src/kapynis/cli/templates/`.

---

## Configuration

Every boot decision is **env-driven** (just like candi). The `.env` generated by `kapynis init` contains only the toggles relevant to your selections:

```bash
SERVICE_NAME=my-service
ENVIRONMENT=development

# Which servers/workers boot
USE_REST=true
USE_GRPC=false
USE_GRAPHQL=false
USE_CRON_SCHEDULER=false
USE_KAFKA_CONSUMER=false
USE_REDIS_SUBSCRIBER=false
USE_RABBITMQ_WORKER=false
USE_POSTGRES_LISTENER=false
USE_TASK_QUEUE_WORKER=false

# REST framework selection (FastAPI default, Litestar alternative)
REST_FRAMEWORK=fastapi

# Ports
HTTP_PORT=8000
GRPC_PORT=9000

# Datastores (only included when selected during init)
SQL_DSN_WRITE=postgresql+asyncpg://postgres:postgres@localhost:5432/my_service
REDIS_DSN_WRITE=redis://localhost:6379/0

MAX_CONCURRENT_TASKS=10
```

All env vars are parsed into a [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) `Env` class — see [`src/kapynis/config/env.py`](src/kapynis/config/env.py) for the full schema.

---

## Generated service layout

```
my-service/
├── main.py                          ← entry point
├── pyproject.toml                   ← pip install -e .
├── .env                             ← env vars (gitignored)
├── kapynis.json                     ← scaffolding config (mirrors candi.json)
├── Makefile
├── alembic.ini
├── alembic/
│   └── env.py                       ← imports from src.pkg.shared.domain
└── src/                             ← Python package (src/__init__.py)
    ├── internal/
    │   ├── service.py               ← ServiceFactory wiring
    │   └── modules/
    │       └── expense/
    │           ├── module.py
    │           ├── domain/          ← Pydantic DTOs (Request / Filter)
    │           ├── delivery/        ← rest_handler.py
    │           ├── usecase/         ← usecase.py
    │           └── repository/      ← repository.py + repo_sql.py
    ├── pkg/
    │   └── shared/
    │       ├── domain/              ← SQLAlchemy models (registered with Alembic)
    │       ├── repository/          ← SharedRepository UOW singleton
    │       └── usecase/             ← SharedUsecase UOW singleton
    └── configs/
        └── config.py                ← LoadServiceConfigs (DB, broker, deps)
```

All imports follow a clear two-namespace convention:

```python
# kapynis framework — installed via pip, shows provenance like Go's module path
from kapynis.codebase.factory.dependency import Dependency
from kapynis.codebase.interfaces.rest_router import RESTRouter
from kapynis.wrapper.http_response import HTTPResponse

# service-local code — always prefixed with src.
from src.internal.modules.expense.domain import CreateExpenseRequest
from src.pkg.shared.usecase.usecase import get_shared_usecase
```

---

## Architecture cheat sheet

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

    REST/gRPC/GraphQL handler ──► Usecase ──► Repository ──► DB
                                    │
                                    └─► shared_usecase (cross-module)
```

| Layer | Where it lives | Responsibility |
|---|---|---|
| **Delivery** | `src/internal/modules/<m>/delivery/` | HTTP / gRPC / worker glue. Reads `domain.Request*`, calls usecase, writes `HTTPResponse`. |
| **Usecase** | `src/internal/modules/<m>/usecase/` | Business logic. Holds repo, cache, locker, publishers, sibling-module bridge. |
| **Repository** | `src/internal/modules/<m>/repository/` | Data access. Uses `with_transaction` (contextvar) so nested calls share one session. |
| **Domain** | `src/internal/modules/<m>/domain/` | Pydantic DTOs (Request / Response / Filter). |
| **Shared DB models** | `src/pkg/shared/domain/` | SQLAlchemy declarative models — registered with Alembic. |
| **Shared UOW** | `src/pkg/shared/{repository,usecase}/` | Singleton aggregators with `# @kapynis:*` markers — each `add-module` call extends them. |

---

## Swap the REST engine

The framework ships two `RESTRouter` adapters. Pick at boot:

```bash
REST_FRAMEWORK=fastapi python main.py     # default
REST_FRAMEWORK=litestar python main.py    # alternative
```

Module handlers are unchanged — they only depend on the abstract `RESTRouter` Protocol. To plug in yet another engine (Sanic, BlackSheep, …) install the matching package from [kapynis-plugin](https://github.com/santosodb/kapynis-plugin) and register its `AppServerFactory` in `src/internal/service.py`.

---

## Plugins

Optional adapters live in [`kapynis-plugin`](https://github.com/santosodb/kapynis-plugin) — mirrors candi-plugin:

- `kapynis-sanic-rest` / `kapynis-blacksheep-rest` — alternative REST engines
- `kapynis-gcp-pubsub` / `kapynis-aws-sqs` / `kapynis-stomp-broker` — additional brokers
- `kapynis-arangodb` / `kapynis-oracledb` — additional storage adapters
- `kapynis-tracer-otlp` — OTLP span exporter for the OpenTelemetry tracer
- `kapynis-circuit-breaker` — resilience middleware
- `kapynis-p2p` — libp2p `AppServerFactory`
- `kapynis-task-queue-admin` — enhanced TaskQueue with GraphQL admin UI

---

## Framework layout

```
kapynis/
├── pyproject.toml              ← setuptools, src layout, PyPI metadata
├── setup.py                    ← package-dir shim (maps kapynis.* → src/kapynis/*)
├── Makefile
├── CLAUDE.md                   ← contributor / AI context
├── examples/                   ← sample services
├── tests/unit/                 ← 26 passing unit tests
└── src/kapynis/                ← the framework package
    ├── codebase/               ← Protocols + factories + 11 server/worker apps
    ├── config/                 ← Env (pydantic-settings) + DB / broker init
    ├── shared/                 ← Meta, Filter, TokenClaim, PublisherArgument
    ├── helper/                 ← MultiError, string_case, query_param
    ├── utils/                  ← RedisLocker
    ├── logger/  tracer/        ← structlog JSON + OpenTelemetry
    ├── wrapper/                ← HTTPResponse envelope + built-in middleware
    ├── middleware/             ← Bearer / Basic / ACL guards
    ├── validator/              ← JSON-Schema + Pydantic
    ├── repository/             ← BaseSQLRepository + with_transaction
    ├── usecase/                ← BaseUsecase + UOW singletons
    └── cli/                    ← Click commands + Jinja2 templates
```

**src layout** — `src/kapynis/` is the physical package directory. IDEs (PyCharm, VS Code Pylance) resolve `from kapynis.xxx import ...` without any extra configuration.

---

## Development

```bash
make test           # pytest tests/unit
make lint           # ruff check
make typecheck      # mypy --strict
make format         # ruff format + autofix
```

The repo ships 26 unit tests covering: `Meta`, `Filter`, `MultiError`, `HTTPResponse`, `SharedSingleton` (idempotency), marker injection, cron pattern parsing, string case conversion. They run in under a second and require no external services.

CLI smoke test:

```bash
kapynis init        # answer the wizard, name it demo-svc with one module
cd demo-svc
python -m py_compile src/internal/service.py
python -m py_compile src/internal/modules/*/usecase/usecase.py
```

If those compile, the framework + templates + marker engine are all healthy.

---

## How `kapynis` compares to `candi`

| Concept | candi (Go) | kapynis (Python) |
|---|---|---|
| Service factory | `factory.ServiceFactory` interface | `ServiceFactory` Protocol |
| App server factory | `factory.AppServerFactory` (Serve/Shutdown/Name) | async `serve()` / `shutdown()` / `name` |
| Dependency container | `dependency.Dependency` + `stdDeps` singleton | `Dependency` + module-level `_std_deps` (free-function getters) |
| Shared UOW | `sync.Once` + `SetSharedUsecase/RepoSQL` | `threading.Lock` + `SharedSingleton[T]` |
| Cross-module bridge | `common.SetCommonUsecase` | `kapynis.usecase.singleton.set_common_usecase` |
| Transaction in context | `RepoSQL.WithTransaction(ctx, fn)` | `with_transaction(session_factory)` using `contextvars.ContextVar` |
| Response envelope | `wrapper.NewHTTPResponse(...)` | `HTTPResponse.new(...).to_response()` |
| Module imports | `github.com/user/svc/internal/...` | `from src.internal.modules.xxx import ...` |
| Framework imports | `github.com/golangid/candi/...` | `from kapynis.codebase.xxx import ...` |
| Code-gen markers | `// @candi:usecaseMethod`, … | `# @kapynis:usecaseMethod`, … |
| Migrations | goose | Alembic (autogenerate) |
| Logger / tracer | zap / OpenTracing | structlog / OpenTelemetry |
| CLI | `candi -init` / `-add-module` / `-add-handler` | `kapynis init` / `add-module` / `add-handler` |

---

## License

See [`LICENSE`](LICENSE).
