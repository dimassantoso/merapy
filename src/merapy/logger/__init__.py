"""structlog-based JSON logger with automatic trace_id injection.

Every log line emitted within a traced context automatically includes a
``trace_id`` field — enabling log/trace correlation in Jaeger, Loki, etc.
This mirrors candi's approach of logging the trace URL after each request/job.

The trace_id is injected via two mechanisms:
1. ``_trace_id_processor`` — reads the current OTel span at log time and
   injects ``trace_id`` into the event dict (works even without explicit binding).
2. ``bind_trace_context()`` in ``merapy.tracer`` — explicitly binds trace_id
   to structlog contextvars at the start of each request/job for persistence
   across async boundaries.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def _trace_id_processor(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Structlog processor that injects the current OTel trace_id.

    Reads the active span from OTel's contextvars at log time. This is a
    fallback for cases where ``bind_trace_context()`` was not called — it
    ensures trace_id is always present when a span is active.

    If ``trace_id`` is already in the event dict (set by merge_contextvars),
    this processor is a no-op to avoid overwriting an explicitly bound value.
    """
    if "trace_id" not in event_dict:
        try:
            from opentelemetry import trace
            span = trace.get_current_span()
            ctx = span.get_span_context()
            if ctx is not None and ctx.trace_id != 0:
                event_dict["trace_id"] = format(ctx.trace_id, "032x")
        except Exception:
            pass
    return event_dict


def init_logger(*, service: str, debug: bool = False) -> None:
    """Configure structlog for JSON output to stdout.

    Idempotent — safe to call multiple times. Call once during boot from
    ``configs.load_service_configs``.

    The processor chain:
    1. merge_contextvars   — pulls in trace_id bound by bind_trace_context()
    2. _trace_id_processor — fallback: reads OTel span directly at log time
    3. add_log_level       — adds "level" field
    4. TimeStamper         — adds ISO-8601 "timestamp" field
    5. StackInfoRenderer   — renders stack_info if present
    6. format_exc_info     — renders exception info if present
    7. JSONRenderer        — serializes to JSON
    """
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _trace_id_processor,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    structlog.contextvars.bind_contextvars(service=service)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name) if name else structlog.get_logger()
