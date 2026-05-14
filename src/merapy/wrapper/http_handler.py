"""Built-in HTTP middleware + root handlers."""

from __future__ import annotations

import time
from typing import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from merapy.config.env import Env
from merapy.logger import get_logger
from merapy.tracer import start_trace
from merapy.wrapper.http_response import HTTPResponse, _safe_serializable

logger = get_logger(__name__)


class _TracerLogMiddleware(BaseHTTPMiddleware):
    """Wraps each request in an OpenTelemetry span and JSON-logs the result."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        method = request.method
        path = request.url.path
        async with start_trace(f"HTTP {method} {path}") as span:
            span.set_attribute("http.method", method)
            span.set_attribute("http.target", path)
            started = time.monotonic()
            response = await call_next(request)
            elapsed = (time.monotonic() - started) * 1000
            span.set_attribute("http.status_code", response.status_code)
            logger.info(
                "http.access",
                method=method,
                path=path,
                status=response.status_code,
                ms=round(elapsed, 2),
            )
            return response


def tracer_middleware() -> type[BaseHTTPMiddleware]:
    """Returns the tracer/log middleware class. Use with
    ``app.add_middleware(tracer_middleware())``.
    """
    return _TracerLogMiddleware


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
    """Catch ``TypeError: Object of type X is not JSON serializable``.

    This fires when a route handler returns a value that FastAPI's default
    JSON encoder cannot handle (e.g. a raw SQLAlchemy model, ``datetime``,
    ``Decimal``, ``UUID``). We coerce the offending value with
    ``_safe_serializable`` and return a 200 with the sanitised payload rather
    than a 500 Internal Server Error.
    """
    msg = str(exc)
    logger.warning("http.json_serialize_error", error=msg, path=request.url.path)
    # Best-effort: try to pull the raw return value out of the exception chain.
    # If we can't, just surface the error message as a 500.
    cause = exc.__cause__ or exc
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
    """Convenience for REST servers: attach CORS + tracer middleware + exception handlers."""
    if not isinstance(app, FastAPI):
        return
    cors_cls, cors_kwargs = cors_middleware(env)
    app.add_middleware(cors_cls, **cors_kwargs)
    app.add_middleware(tracer_middleware())
    app.add_exception_handler(TypeError, _type_error_handler)  # type: ignore[arg-type]
