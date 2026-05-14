"""OpenTelemetry tracer — span lifecycle, W3C propagation, trace ID utilities.

Mirrors candi's tracer package (Go) ported to Python using OTel's contextvars-
based context propagation instead of explicit ctx passing.

Key differences from Go:
- Python OTel uses contextvars — start_as_current_span sets the active span
  implicitly; child spans find their parent without explicit ctx threading.
- asyncio.create_task does NOT inherit contextvars — use
  ``asyncio.create_task(coro(), context=contextvars.copy_context())`` when
  spawning tasks that must continue the current trace.

Public API
----------
init_tracer(service)            — initialize TracerProvider (idempotent)
set_jaeger_base_url(url)        — configure Jaeger UI URL for trace links
get_trace_id()                  — current trace_id as 32-hex string or ""
get_trace_url(base_url=None)    — Jaeger UI URL for current trace or ""
start_trace(name)               — async ctx manager: child span (or root)
start_trace_from_header(name, headers) — async ctx manager: root span from W3C traceparent
log_to_span(event, **attrs)     — add event to current span (no-op if none)
inject_trace_headers(headers)   — inject traceparent into outgoing headers
bind_trace_context()            — bind trace_id to structlog contextvars
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.propagate import extract as _otel_extract
from opentelemetry.propagate import inject as _otel_inject
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

_log = logging.getLogger(__name__)

# Module-level state
_initialized: bool = False
_jaeger_base_url: str = ""


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def init_tracer(service: str, *, console_export: bool = False) -> None:
    """Initialize the global TracerProvider with the given service name.

    Idempotent — safe to call multiple times. Subsequent calls are no-ops.
    When ``console_export`` is True, spans are echoed to stdout (dev only).
    OTLP exporters can be added afterwards via ``merapy_tracer_otlp``.
    """
    global _initialized
    if _initialized:
        return
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service}))
    if console_export:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    _initialized = True


def set_jaeger_base_url(url: str) -> None:
    """Configure the Jaeger UI base URL used by ``get_trace_url()``.

    Example::

        set_jaeger_base_url("http://localhost:16686")
        # get_trace_url() → "http://localhost:16686/trace/<trace_id>"
    """
    global _jaeger_base_url
    _jaeger_base_url = url.rstrip("/")


# ---------------------------------------------------------------------------
# Tracer accessor
# ---------------------------------------------------------------------------

def get_tracer(name: str = "merapy") -> trace.Tracer:
    """Return a named OTel Tracer instance."""
    return trace.get_tracer(name)


# ---------------------------------------------------------------------------
# Trace ID + URL utilities
# ---------------------------------------------------------------------------

def get_trace_id() -> str:
    """Return the current trace_id as a 32-character lowercase hex string.

    Returns an empty string when no span is active or the TracerProvider has
    not been initialized (no-op span context has trace_id == 0).
    """
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx is None or ctx.trace_id == 0:
        return ""
    return format(ctx.trace_id, "032x")


def get_trace_url(base_url: str | None = None) -> str:
    """Return the Jaeger UI URL for the current trace.

    Uses ``base_url`` if provided, otherwise falls back to the module-level
    URL set by ``set_jaeger_base_url()``. Returns empty string when either
    the URL is not configured or no span is active.

    Example::

        url = get_trace_url()
        # → "http://localhost:16686/trace/abc123..."
    """
    url = (base_url or _jaeger_base_url).rstrip("/")
    if not url:
        return ""
    tid = get_trace_id()
    if not tid:
        return ""
    return f"{url}/trace/{tid}"


# ---------------------------------------------------------------------------
# Span creation
# ---------------------------------------------------------------------------

@asynccontextmanager
async def start_trace(name: str) -> AsyncIterator[trace.Span]:
    """Async context manager that creates a child span (or root if none active).

    The span is automatically ended when the context manager exits, even on
    exception. Exceptions propagate normally — the span status is NOT set to
    ERROR automatically; callers should set it explicitly if needed.

    Usage::

        async with start_trace("ExpenseUsecase:GetAll") as span:
            span.set_attribute("filter.search", filter.search or "")
            result = await repo.fetch_all(filter)
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        yield span


@asynccontextmanager
async def start_trace_from_header(
    name: str,
    headers: dict[str, str],
) -> AsyncIterator[trace.Span]:
    """Async context manager that extracts W3C traceparent from headers.

    If a valid ``traceparent`` header is present, the created span continues
    the remote trace (same trace_id). If absent or malformed, a new root span
    is created with a fresh trace_id.

    This is the entry-point for all delivery-layer spans (HTTP middleware,
    Kafka consumer, RabbitMQ consumer) — mirrors candi's
    ``tracer.StartTraceFromHeader``.

    Usage::

        async with start_trace_from_header("HTTP GET /api", dict(request.headers)) as span:
            span.set_attribute("http.method", "GET")
            ...
    """
    # Extract parent context from W3C traceparent/tracestate headers.
    # OTel's extract() returns an empty context if headers are absent/invalid —
    # the SDK then creates a new root span automatically.
    parent_ctx = _otel_extract(headers)
    token = otel_context.attach(parent_ctx)
    try:
        tracer = get_tracer()
        with tracer.start_as_current_span(name) as span:
            yield span
    finally:
        otel_context.detach(token)


# ---------------------------------------------------------------------------
# Span event logging
# ---------------------------------------------------------------------------

def log_to_span(event_name: str, **attributes: object) -> None:
    """Add a timestamped event to the current active span.

    Equivalent to candi's ``trace.Log(key, value)`` — events appear as logs
    in the Jaeger span timeline. No-op when no span is active or the span is
    not recording.

    Usage::

        log_to_span("http.request.body", body=body_str)
        log_to_span("task.arguments", args=job.arguments)
    """
    span = trace.get_current_span()
    if span.is_recording():
        # OTel span events require attribute values to be str/int/float/bool
        # or sequences thereof. Coerce everything to str for safety.
        safe_attrs = {k: str(v) if not isinstance(v, (str, int, float, bool)) else v
                      for k, v in attributes.items()}
        span.add_event(event_name, attributes=safe_attrs)


# ---------------------------------------------------------------------------
# Outgoing header injection
# ---------------------------------------------------------------------------

def inject_trace_headers(headers: dict[str, str]) -> dict[str, str]:
    """Inject W3C ``traceparent`` (and ``tracestate``) into ``headers``.

    Mutates and returns the same dict. No-op when no span is active.
    Use this before making outgoing HTTP calls to propagate the trace.

    Usage::

        headers = inject_trace_headers({"Content-Type": "application/json"})
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://other-service/api", headers=headers)
    """
    _otel_inject(headers)
    return headers


# ---------------------------------------------------------------------------
# Log correlation
# ---------------------------------------------------------------------------

def bind_trace_context() -> None:
    """Bind the current trace_id to structlog context vars.

    After this call, all structlog log lines emitted in the current async
    context will include a ``trace_id`` field — enabling log/trace correlation
    in log aggregators (Loki, Elasticsearch, etc.).

    Call this immediately after starting a root span in middleware or workers.
    No-op when no span is active.
    """
    tid = get_trace_id()
    if tid:
        structlog.contextvars.bind_contextvars(trace_id=tid)


# ---------------------------------------------------------------------------
# Backward-compatible re-exports
# ---------------------------------------------------------------------------

__all__ = [
    "init_tracer",
    "set_jaeger_base_url",
    "get_tracer",
    "get_trace_id",
    "get_trace_url",
    "start_trace",
    "start_trace_from_header",
    "log_to_span",
    "inject_trace_headers",
    "bind_trace_context",
]
