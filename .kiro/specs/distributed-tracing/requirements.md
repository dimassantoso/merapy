# Requirements Document

## Introduction

End-to-end distributed tracing for the merapy Python microservice framework, matching the candi (Go) tracing pattern. This feature provides full observability across HTTP requests and all worker types (TaskQueue, Kafka, Cron, Redis, RabbitMQ, Postgres Listener) by creating OpenTelemetry traces with proper parent-child span hierarchies, SQL query tracing, log correlation via trace_id, and Jaeger dashboard integration.

## Glossary

- **Tracer_Module**: The central tracing utility module (`tracer/__init__.py`) providing span creation, trace ID extraction, header propagation, and trace URL generation
- **SQL_Tracer**: The SQLAlchemy event hook component (`tracer/sql_tracer.py`) that creates child spans for database queries
- **HTTP_Middleware**: The Starlette/FastAPI middleware (`wrapper/http_handler.py`) that creates root spans per HTTP request
- **Logger**: The structlog-based logging component (`logger/__init__.py`) with automatic trace_id injection
- **TaskQueue_Worker**: The background job worker that processes queued tasks and persists trace_id to job records
- **Worker**: Any of the background processing components (Kafka, Cron, Redis, RabbitMQ, Postgres Listener) that create root spans per job/message
- **W3C_Traceparent**: The W3C Trace Context propagation header format (`traceparent: 00-{trace_id}-{span_id}-{flags}`)
- **Root_Span**: The top-level span created at the entry point of a request or job
- **Child_Span**: A span nested under a parent span within the same trace
- **Trace_URL**: A clickable Jaeger UI URL in the format `{base_url}/trace/{trace_id}`
- **OTLP**: OpenTelemetry Protocol used to export spans to Jaeger
- **Span_Event**: A timestamped annotation attached to a span (used for body logging)

## Requirements

### Requirement 1: Tracer Module Initialization and Span Creation

**User Story:** As a developer, I want a central tracer module that handles span lifecycle management, so that I can instrument any code path with minimal boilerplate.

#### Acceptance Criteria

1. WHEN `init_tracer(service)` is called, THE Tracer_Module SHALL configure a global TracerProvider with the given service name
2. WHEN `init_tracer(service)` is called multiple times, THE Tracer_Module SHALL be idempotent and not create duplicate providers
3. WHEN `start_trace(name)` is called within an active span context, THE Tracer_Module SHALL create a Child_Span parented to the current active span
4. WHEN `start_trace(name)` is called without an active span context, THE Tracer_Module SHALL create a new Root_Span
5. WHEN a span created by `start_trace` exits its context manager, THE Tracer_Module SHALL end the span and export it via the configured exporter

### Requirement 2: Trace ID Extraction and URL Generation

**User Story:** As a developer, I want to retrieve the current trace ID and generate Jaeger URLs, so that I can correlate logs and provide clickable links to traces.

#### Acceptance Criteria

1. WHEN an active span exists, THE Tracer_Module SHALL return the trace_id as a 32-character lowercase hexadecimal string via `get_trace_id()`
2. WHEN no active span exists, THE Tracer_Module SHALL return an empty string from `get_trace_id()`
3. WHEN `get_trace_url()` is called with a configured Jaeger base URL and an active span, THE Tracer_Module SHALL return a URL in the format `{base_url}/trace/{trace_id}`
4. WHEN `get_trace_url()` is called without a configured Jaeger base URL, THE Tracer_Module SHALL return an empty string
5. WHEN `get_trace_url()` is called without an active span, THE Tracer_Module SHALL return an empty string

### Requirement 3: W3C Trace Context Propagation

**User Story:** As a developer, I want trace context to propagate across service boundaries via HTTP headers, so that distributed traces are linked across microservices.

#### Acceptance Criteria

1. WHEN `start_trace_from_header(name, headers)` is called with a valid W3C_Traceparent header, THE Tracer_Module SHALL create a span whose trace_id matches the extracted trace_id from the header
2. WHEN `start_trace_from_header(name, headers)` is called with missing or invalid traceparent header, THE Tracer_Module SHALL create a new Root_Span with a freshly generated trace_id
3. WHEN `inject_trace_headers(headers)` is called with an active span, THE Tracer_Module SHALL add a valid `traceparent` key to the headers dict
4. WHEN `inject_trace_headers(headers)` is called, THE Tracer_Module SHALL preserve all existing keys in the headers dict
5. WHEN `inject_trace_headers(headers)` is called without an active span, THE Tracer_Module SHALL return the headers dict unchanged

### Requirement 4: Span Event Logging

**User Story:** As a developer, I want to attach structured events to spans, so that request/response bodies and job arguments are visible in Jaeger.

#### Acceptance Criteria

1. WHEN `log_to_span(event_name, **attributes)` is called with a recording span active, THE Tracer_Module SHALL add an event with the given name and attributes to the current span
2. WHEN `log_to_span(event_name, **attributes)` is called without an active span, THE Tracer_Module SHALL perform no operation and raise no exception
3. WHEN a request or response body exceeds TRACE_BODY_MAX_SIZE (64KB), THE HTTP_Middleware SHALL truncate the body to the max size and append a `[truncated]` marker

### Requirement 5: SQL Query Tracing

**User Story:** As a developer, I want every SQL query to produce a child span automatically, so that I can see database performance within traces without manual instrumentation.

#### Acceptance Criteria

1. WHEN `instrument_engine(engine)` is called, THE SQL_Tracer SHALL attach event listeners to the engine for `before_cursor_execute`, `after_cursor_execute`, and `handle_error` events
2. WHEN a SQL query is executed within a traced context, THE SQL_Tracer SHALL create a Child_Span with `db.statement` and `db.system` attributes
3. WHEN a SQL query completes successfully, THE SQL_Tracer SHALL set the `db.rows_affected` attribute on the span
4. IF a SQL query raises an exception, THEN THE SQL_Tracer SHALL set the span status to ERROR with the exception message and end the span
5. IF an exception occurs within the SQL_Tracer event hook logic itself, THEN THE SQL_Tracer SHALL catch the exception, log a warning, and allow the query to proceed unblocked

### Requirement 6: HTTP Middleware Tracing

**User Story:** As a developer, I want every HTTP request to be automatically traced with full context, so that I get end-to-end visibility without modifying handler code.

#### Acceptance Criteria

1. WHEN an HTTP request is received, THE HTTP_Middleware SHALL extract W3C_Traceparent from request headers and create a Root_Span
2. WHEN a Root_Span is created for an HTTP request, THE HTTP_Middleware SHALL set `http.method`, `http.url_path`, and `http.status_code` as span attributes
3. WHEN a Root_Span is created for an HTTP request, THE HTTP_Middleware SHALL bind the trace_id to structlog context vars for log correlation
4. WHEN an HTTP request has a body, THE HTTP_Middleware SHALL log the request body as a span event named `http.request.body`
5. WHEN an HTTP response is produced, THE HTTP_Middleware SHALL log the response body as a span event named `http.response.body`
6. WHEN an HTTP request completes and JAEGER_BASE_URL is configured, THE HTTP_Middleware SHALL log the Trace_URL to stdout

### Requirement 7: Logger Trace Correlation

**User Story:** As a developer, I want every log line to automatically include the trace_id, so that I can search logs by trace and correlate them with Jaeger spans.

#### Acceptance Criteria

1. THE Logger SHALL include a structlog processor that injects `trace_id` into every log event dict when an active span exists
2. WHEN no active span exists, THE Logger SHALL emit log lines without a `trace_id` field
3. WHEN `bind_trace_context()` is called with an active span, THE Logger SHALL bind the current trace_id to structlog context vars so all subsequent logs in that context include it

### Requirement 8: TaskQueue Worker Tracing

**User Story:** As a developer, I want TaskQueue jobs to be traced with trace_id persisted to the database, so that I can link dashboard job records to their Jaeger traces.

#### Acceptance Criteria

1. WHEN a TaskQueue job is executed with `disable_trace=False`, THE TaskQueue_Worker SHALL create a Root_Span named `TaskQueue:{module}:{task_name}`
2. WHEN a Root_Span is created for a TaskQueue job, THE TaskQueue_Worker SHALL set `task.name`, `task.id`, `task.retries`, and `task.max_retry` as span attributes
3. WHEN a Root_Span is created for a TaskQueue job, THE TaskQueue_Worker SHALL persist the trace_id to the job record in the database
4. WHEN a TaskQueue job completes and JAEGER_BASE_URL is configured, THE TaskQueue_Worker SHALL log the Trace_URL to stdout
5. WHEN a handler entry has `disable_trace=True`, THE TaskQueue_Worker SHALL execute the handler without creating a span

### Requirement 9: Message Broker Worker Tracing (Kafka, RabbitMQ)

**User Story:** As a developer, I want Kafka and RabbitMQ workers to extract trace context from message headers, so that traces span across producers and consumers.

#### Acceptance Criteria

1. WHEN a Kafka message is received with a valid traceparent header, THE Worker SHALL create a Root_Span as a child of the remote parent trace
2. WHEN a RabbitMQ message is received with a valid traceparent header, THE Worker SHALL create a Root_Span as a child of the remote parent trace
3. WHEN a Kafka message is received without a traceparent header, THE Worker SHALL create a new Root_Span with a fresh trace_id
4. WHEN a Kafka Root_Span is created, THE Worker SHALL set `kafka.topic`, `kafka.key`, and `kafka.consumer_group` as span attributes
5. WHEN a message broker worker job completes and JAEGER_BASE_URL is configured, THE Worker SHALL log the Trace_URL to stdout

### Requirement 10: Scheduled and Event Worker Tracing (Cron, Redis, Postgres)

**User Story:** As a developer, I want Cron, Redis, and Postgres Listener workers to create root spans per tick/message/notification, so that all background work is observable in Jaeger.

#### Acceptance Criteria

1. WHEN a Cron tick fires, THE Worker SHALL create a Root_Span with `cron.pattern` and `cron.module` as span attributes
2. WHEN a Redis message is received, THE Worker SHALL create a Root_Span with `channel` as a span attribute
3. WHEN a Postgres notification is received, THE Worker SHALL create a Root_Span with `channel` as a span attribute
4. WHEN any worker Root_Span is created, THE Worker SHALL bind the trace_id to structlog context vars for log correlation
5. WHEN any worker job completes and JAEGER_BASE_URL is configured, THE Worker SHALL log the Trace_URL to stdout

### Requirement 11: Dashboard Trace Link

**User Story:** As a developer, I want the TaskQueue dashboard to display trace_id as a clickable Jaeger link, so that I can jump directly from a job to its trace.

#### Acceptance Criteria

1. WHEN a job record has a non-empty `trace_id` field, THE Dashboard SHALL render the trace_id as a clickable hyperlink pointing to `{JAEGER_BASE_URL}/trace/{trace_id}`
2. WHEN a job record has an empty or null `trace_id` field, THE Dashboard SHALL display a dash or empty indicator without a link

### Requirement 12: Error Resilience

**User Story:** As a developer, I want tracing to never break application functionality, so that observability failures are gracefully degraded without impacting business logic.

#### Acceptance Criteria

1. IF the TracerProvider is not initialized, THEN THE Tracer_Module SHALL return no-op spans and empty strings without raising exceptions
2. IF the OTLP exporter endpoint is unreachable, THEN THE Tracer_Module SHALL buffer spans and drop oldest when the buffer is full without blocking the application
3. IF a SQL_Tracer event hook raises an internal exception, THEN THE SQL_Tracer SHALL catch it and allow the query to execute normally
4. IF an incoming traceparent header is malformed, THEN THE Tracer_Module SHALL create a new root trace instead of propagating an error
