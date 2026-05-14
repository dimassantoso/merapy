"""OpenTelemetry tracer init + start_trace helpers. Mirrors candi's OpenTracing wrapper."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

_initialized = False


def init_tracer(service: str, *, console_export: bool = False) -> None:
    """Initialize the global tracer provider.

    Idempotent. When ``console_export`` is true, spans are echoed to stdout —
    useful in development. Exporters for OTLP / Jaeger can be added by the
    generated service.
    """
    global _initialized
    if _initialized:
        return
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service}))
    if console_export:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    _initialized = True


def get_tracer(name: str = "merapy") -> trace.Tracer:
    return trace.get_tracer(name)


@asynccontextmanager
async def start_trace(name: str) -> AsyncIterator[trace.Span]:
    """Async context manager wrapping ``tracer.start_as_current_span``.

    Mirrors candi's ``tracer.StartTraceWithContext`` ergonomics::

        async with start_trace("ExpenseUsecase:GetAll") as span:
            span.set_attribute("filter.search", filter.search or "")
            ...
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        yield span
