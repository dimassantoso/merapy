"""Built-in HTTP middleware + root handlers.

The tracer middleware mirrors candi's HTTPMiddlewareTracer:
- Extracts W3C traceparent from incoming request headers
- Creates a root span (or continues a remote trace)
- Logs request body + response body as span events (capped at TRACE_BODY_MAX_SIZE)
- Binds trace_id to structlog context vars for log correlation
- Logs the Jaeger trace URL to stdout after each request
"""

from __future__ import annotations

import time
from typing import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from merapy.config.env import Env
from merapy.logger import get_logger
from merapy.tracer import (
    bind_trace_context,
    get_trace_url,
    log_to_span,
    start_trace_from_header,
)
from merapy.wrapper.http_response import HTTPResponse, _safe_serializable

logger = get_logger(__name__)

# Paths excluded from tracing (health checks, static assets)
_EXCLUDE_PATHS = frozenset({"/", "/health", "/favicon.ico", "/graphql"})

# Default body size cap — overridden by env.trace_body_max_size
_DEFAULT_BODY_MAX = 65_536  # 64 KB


class _TracerLogMiddleware(BaseHTTPMiddleware):
    """Root span per HTTP request with full observability.

    For each request:
    1. Extract W3C traceparent from headers → start root span
    2. Bind trace_id to structlog context vars
    3. Log request body as span event (truncated if > max_size)
    4. Dispatch to next handler
    5. Log response body as span event (truncated if > max_size)
    6. Set http.status_code, http.method, http.url_path attributes
    7. Log Jaeger trace URL to stdout
    8. Emit structured access log line
    """

    def __init__(self, app: ASGIApp, *, body_max_size: int = _DEFAULT_BODY_MAX) -> None:
        super().__init__(app)
        self._body_max = body_max_size

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        method = request.method
        path = request.url.path

        # Skip tracing for excluded paths (health, favicon, etc.)
        if path in _EXCLUDE_PATHS:
            return await call_next(request)

        # Build header dict for W3C traceparent extraction
        headers = dict(request.headers)
        span_name = f"HTTP {method} {path}"

        async with start_trace_from_header(span_name, headers) as span:
            # Set standard HTTP span attributes
            span.set_attribute("http.method", method)
            span.set_attribute("http.url_path", path)
            span.set_attribute("http.scheme", request.url.scheme)
            span.set_attribute("http.host", request.url.hostname or "")

            # Bind trace_id to structlog for log correlation
            bind_trace_context()

            # Log request body as span event
            await _log_request_body(request, span, self._body_max)

            started = time.monotonic()
            response = await call_next(request)
            elapsed_ms = round((time.monotonic() - started) * 1000, 2)

            # Set response attributes
            span.set_attribute("http.status_code", response.status_code)

            # Log response body as span event (stream-safe)
            response = await _log_response_body(response, span, self._body_max)

            # Mark span as error for 4xx/5xx
            if response.status_code >= 400:
                from opentelemetry.trace import Status, StatusCode
                span.set_status(
                    Status(StatusCode.ERROR, f"HTTP {response.status_code}")
                )

            # Emit structured access log (includes trace_id via processor)
            logger.info(
                "http.access",
                method=method,
                path=path,
                status=response.status_code,
                ms=elapsed_ms,
            )

            # Log Jaeger trace URL (mirrors candi's logger.LogGreen("rest_server > trace_url: ..."))
            trace_url = get_trace_url()
            if trace_url:
                logger.info("http > trace_url", url=trace_url)

            return response


async def _log_request_body(
    request: Request, span: object, max_size: int
) -> None:
    """Read and log the request body as a span event, then restore it."""
    content_length = int(request.headers.get("content-length", 0))
    if content_length <= 0:
        return
    try:
        body = await request.body()
        if not body:
            return
        body_str = _truncate(body.decode("utf-8", errors="replace"), max_size)
        log_to_span("http.request.body", body=body_str)
    except Exception:
        pass  # Never block the request for tracing failures


async def _log_response_body(
    response: Response, span: object, max_size: int
) -> Response:
    """Consume, log, and reconstruct the response body."""
    try:
        # Starlette's StreamingResponse / Response — collect body bytes
        body_chunks: list[bytes] = []
        async for chunk in response.body_iterator:  # type: ignore[attr-defined]
            body_chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode())
        body_bytes = b"".join(body_chunks)
        body_str = _truncate(body_bytes.decode("utf-8", errors="replace"), max_size)
        log_to_span("http.response.body", body=body_str)

        # Reconstruct response with the consumed body
        from starlette.responses import Response as StarletteResponse
        return StarletteResponse(
            content=body_bytes,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
    except Exception:
        return response  # Return original on any failure


def _truncate(text: str, max_size: int) -> str:
    """Truncate text to max_size bytes (UTF-8), appending [truncated] marker."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_size:
        return text
    return encoded[:max_size].decode("utf-8", errors="replace") + " [truncated]"


# ---------------------------------------------------------------------------
# Middleware factories
# ---------------------------------------------------------------------------

def tracer_middleware(body_max_size: int = _DEFAULT_BODY_MAX) -> type[BaseHTTPMiddleware]:
    """Return a configured _TracerLogMiddleware class.

    Usage::

        app.add_middleware(tracer_middleware(body_max_size=env.trace_body_max_size))
    """
    # Dynamically create a subclass with the configured body_max_size baked in
    # so FastAPI's add_middleware (which only accepts a class, not an instance)
    # can instantiate it correctly.
    class _Configured(_TracerLogMiddleware):
        def __init__(self, app: ASGIApp) -> None:
            super().__init__(app, body_max_size=body_max_size)

    return _Configured


def cors_middleware(env: Env) -> tuple[type[CORSMiddleware], dict[str, object]]:
    """Returns ``(CORSMiddleware, kwargs)`` for ``app.add_middleware``."""
    return CORSMiddleware, {
        "allow_origins": env.cors_allow_origins,
        "allow_methods": env.cors_allow_methods,
        "allow_headers": env.cors_allow_headers,
        "allow_credentials": env.cors_allow_credentials,
    }


def health_response(service: str, env: str) -> HTTPResponse:
    """Standard root-handler response."""
    return HTTPResponse.new(
        200,
        "service alive",
        {"service": service, "environment": env, "framework": "merapy"},
    )


async def _type_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch ``TypeError: Object of type X is not JSON serializable``."""
    msg = str(exc)
    logger.warning("http.json_serialize_error", error=msg, path=request.url.path)
    return JSONResponse(
        status_code=500,
        content=HTTPResponse(
            success=False,
            code=500,
            message="Response serialization error",
            errors={"_": [msg]},
        ).model_dump(exclude_none=True),
    )


def _install_middlewares(app: ASGIApp, env: Env) -> None:
    """Attach CORS + tracer middleware + exception handlers to a FastAPI app."""
    if not isinstance(app, FastAPI):
        return
    cors_cls, cors_kwargs = cors_middleware(env)
    app.add_middleware(cors_cls, **cors_kwargs)
    app.add_middleware(tracer_middleware(body_max_size=env.trace_body_max_size))
    app.add_exception_handler(TypeError, _type_error_handler)  # type: ignore[arg-type]
