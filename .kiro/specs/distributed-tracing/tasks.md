# Tasks

## Task 1: Enhance Tracer Module Core Functions

**Requirements:** 1, 2, 3, 4, 12

**Description:** Rewrite `src/merapy/tracer/__init__.py` to add `get_trace_id()`, `get_trace_url()`, `start_trace_from_header()`, `inject_trace_headers()`, `log_to_span()`, `bind_trace_context()`, `set_jaeger_base_url()`. Keep existing `init_tracer()`, `get_tracer()`, `start_trace()` but enhance them.

**Files to modify:**
- `src/merapy/tracer/__init__.py`

**Acceptance criteria addressed:**
- 1.1–1.5: init_tracer idempotent, start_trace creates child/root spans
- 2.1–2.5: get_trace_id returns 32-hex or empty, get_trace_url constructs URL
- 3.1–3.5: start_trace_from_header extracts W3C traceparent, inject_trace_headers adds traceparent
- 4.1–4.2: log_to_span adds events or no-ops safely
- 12.1, 12.4: no-op when uninitialized, graceful on malformed headers

---

## Task 2: Add JAEGER_BASE_URL and TRACE_BODY_MAX_SIZE to Env Config

**Requirements:** 2, 4, 6

**Description:** Add `JAEGER_BASE_URL` and `TRACE_BODY_MAX_SIZE` fields to `src/merapy/config/env.py` so they're available from `get_env()`. Wire `set_jaeger_base_url()` call during service boot.

**Files to modify:**
- `src/merapy/config/env.py`

**Acceptance criteria addressed:**
- 2.3–2.5: Jaeger base URL configuration
- 4.3: Body max size configuration
- 6.6: Trace URL logging requires configured base URL

---

## Task 3: Create SQL Tracer Module

**Requirements:** 5, 12

**Description:** Create `src/merapy/tracer/sql_tracer.py` with `instrument_engine(engine)` that attaches SQLAlchemy event listeners (`before_cursor_execute`, `after_cursor_execute`, `handle_error`) to create child spans per query.

**Files to create:**
- `src/merapy/tracer/sql_tracer.py`

**Acceptance criteria addressed:**
- 5.1: Attach event listeners to engine
- 5.2: Create child span with db.statement, db.system
- 5.3: Set db.rows_affected after execution
- 5.4: Set span status ERROR on query exception
- 5.5: Catch internal hook exceptions, never block queries
- 12.3: Error resilience in SQL hooks

---

## Task 4: Enhance HTTP Middleware with Full Tracing

**Requirements:** 4, 6, 7

**Description:** Rewrite `_TracerLogMiddleware` in `src/merapy/wrapper/http_handler.py` to: extract `traceparent` from request headers via `start_trace_from_header`, log request/response bodies as span events (with truncation), bind trace_id to structlog, log trace URL after completion.

**Files to modify:**
- `src/merapy/wrapper/http_handler.py`

**Acceptance criteria addressed:**
- 4.3: Body truncation at TRACE_BODY_MAX_SIZE
- 6.1: Extract W3C traceparent and create root span
- 6.2: Set http.method, http.url_path, http.status_code attributes
- 6.3: Bind trace_id to structlog context vars
- 6.4: Log request body as span event
- 6.5: Log response body as span event
- 6.6: Log trace URL to stdout
- 7.3: bind_trace_context() called at request start

---

## Task 5: Enhance Logger with Trace ID Processor

**Requirements:** 7

**Description:** Add a `_trace_id_processor` to structlog's processor chain in `src/merapy/logger/__init__.py` that auto-injects `trace_id` into every log event dict when an active span exists.

**Files to modify:**
- `src/merapy/logger/__init__.py`

**Acceptance criteria addressed:**
- 7.1: Processor injects trace_id when span active
- 7.2: No trace_id field when no span active
- 7.3: bind_trace_context() helper (implemented in tracer module, used here)

---

## Task 6: Enhance TaskQueue Worker with trace_id Persistence

**Requirements:** 8

**Description:** Modify `src/merapy/codebase/app/task_queue_worker/worker.py` `_run()` method to: persist `trace_id` to the job record after span starts, log trace URL after job completes, respect `disable_trace` flag, add `_update_trace_id()` helper method.

**Files to modify:**
- `src/merapy/codebase/app/task_queue_worker/worker.py`

**Acceptance criteria addressed:**
- 8.1: Create root span named TaskQueue:{module}:{task_name}
- 8.2: Set task.name, task.id, task.retries, task.max_retry attributes
- 8.3: Persist trace_id to job record in database
- 8.4: Log trace URL to stdout
- 8.5: Skip span creation when disable_trace=True

---

## Task 7: Add Tracing to Kafka Worker

**Requirements:** 9

**Description:** Modify `src/merapy/codebase/app/kafka_worker/` to extract `traceparent` from Kafka message headers, create root span per message with kafka.topic/key/consumer_group attributes, bind trace_id to structlog, log trace URL.

**Files to modify:**
- `src/merapy/codebase/app/kafka_worker/worker.py` (or equivalent)

**Acceptance criteria addressed:**
- 9.1: Extract traceparent from Kafka headers, create child span
- 9.3: Create new root span when no traceparent
- 9.4: Set kafka.topic, kafka.key, kafka.consumer_group attributes
- 9.5: Log trace URL after completion

---

## Task 8: Add Tracing to RabbitMQ Worker

**Requirements:** 9

**Description:** Modify `src/merapy/codebase/app/rabbitmq_worker/` to extract `traceparent` from message headers, create root span per message, bind trace_id, log trace URL.

**Files to modify:**
- `src/merapy/codebase/app/rabbitmq_worker/worker.py` (or equivalent)

**Acceptance criteria addressed:**
- 9.2: Extract traceparent from RabbitMQ headers, create child span
- 9.5: Log trace URL after completion

---

## Task 9: Add Tracing to Cron, Redis, and Postgres Workers

**Requirements:** 10

**Description:** Modify Cron, Redis subscriber, and Postgres listener workers to create root spans per tick/message/notification with appropriate attributes, bind trace_id, log trace URL.

**Files to modify:**
- `src/merapy/codebase/app/cron_worker/worker.py`
- `src/merapy/codebase/app/redis_worker/worker.py`
- `src/merapy/codebase/app/postgres_worker/worker.py`

**Acceptance criteria addressed:**
- 10.1: Cron span with cron.pattern, cron.module
- 10.2: Redis span with channel attribute
- 10.3: Postgres span with channel attribute
- 10.4: Bind trace_id to structlog for all workers
- 10.5: Log trace URL for all workers

---

## Task 10: Wire SQL Tracer into Database Initialization

**Requirements:** 5

**Description:** Call `instrument_engine(engine)` on both read and write engines during database initialization in `src/merapy/config/database/sql.py` so all queries are automatically traced.

**Files to modify:**
- `src/merapy/config/database/sql.py`

**Acceptance criteria addressed:**
- 5.1: Engine instrumented at boot time
- 5.2–5.5: All queries produce child spans automatically

---

## Task 11: Dashboard Trace Link in Job Detail

**Requirements:** 11

**Description:** Update the task queue dashboard frontend (`app/job/page.tsx`) to render `trace_id` as a clickable Jaeger link. Add `NEXT_PUBLIC_JAEGER_BASE_URL` env var. Show dash when trace_id is empty.

**Files to modify:**
- `/Users/dimas/Documents/Project/personal/merapy-taskqueue-dashboard/app/job/page.tsx`
- `/Users/dimas/Documents/Project/personal/merapy-taskqueue-dashboard/.env.sample`

**Acceptance criteria addressed:**
- 11.1: Clickable hyperlink to {JAEGER_BASE_URL}/trace/{trace_id}
- 11.2: Dash/empty indicator when no trace_id

---

## Task 12: Wire Tracer Init and Jaeger URL in Generated Service Template

**Requirements:** 1, 2

**Description:** Update the CLI service template (`src/merapy/cli/templates/service/`) to call `init_tracer(service_name)` and `set_jaeger_base_url(env.jaeger_base_url)` during boot, and optionally wire `install_otlp_grpc_exporter()` if OTLP is configured.

**Files to modify:**
- `src/merapy/cli/templates/service/src/configs/config.py.j2` (or equivalent boot template)

**Acceptance criteria addressed:**
- 1.1: init_tracer called with service name at boot
- 2.3: Jaeger base URL configured at boot
