"""SQLAlchemy automatic SQL query tracing.

Attaches before/after cursor execute event listeners to a SQLAlchemy
AsyncEngine so every query produces a child OTel span — equivalent to
candi's GORM callback tracing (``AddGormCallbacks`` / ``SetSpanToGorm``).

Usage::

    from merapy.tracer.sql_tracer import instrument_engine

    db = init_sql(env)
    if db:
        instrument_engine(db.read_engine())
        instrument_engine(db.write_engine())

Or via the convenience helper::

    from merapy.tracer.sql_tracer import instrument_sql_database

    instrument_sql_database(db)   # instruments both read + write engines

Span attributes (OpenTelemetry semantic conventions):
    db.system       — "postgresql", "mysql", "sqlite", etc.
    db.statement    — full SQL string (parameterized)
    db.rows_affected — rowcount after execution
    db.operation    — SELECT / INSERT / UPDATE / DELETE / etc.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from merapy.tracer import get_tracer

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

_log = logging.getLogger(__name__)

# Attribute key used to stash the in-flight span on the execution context.
_SPAN_ATTR = "_merapy_sql_span"


def instrument_engine(engine: "AsyncEngine") -> None:
    """Attach SQL tracing event listeners to a SQLAlchemy AsyncEngine.

    Idempotent — calling twice on the same engine is safe (SQLAlchemy
    deduplicates listeners by function identity).

    The listeners run synchronously inside SQLAlchemy's execution pipeline.
    They create/end OTel spans using the *current* OTel context (set by
    ``start_as_current_span`` in the calling coroutine), so SQL spans
    automatically become children of the active usecase/repository span.
    """
    from sqlalchemy import event

    sync_engine = engine.sync_engine

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        try:
            tracer = get_tracer("merapy.sql")
            # Detect db.system from the dialect name
            dialect = getattr(conn, "dialect", None) or getattr(sync_engine, "dialect", None)
            db_system = _dialect_to_system(getattr(dialect, "name", ""))

            # Extract operation keyword (SELECT, INSERT, …)
            operation = _extract_operation(statement)

            span = tracer.start_span(
                f"SQL {operation}",
                attributes={
                    "db.system": db_system,
                    "db.statement": statement,
                    "db.operation": operation,
                },
            )
            # Stash span on the execution context for retrieval in _after/_error
            if context is not None:
                setattr(context, _SPAN_ATTR, span)
        except Exception:
            _log.debug("sql_tracer.before_failed", exc_info=True)

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        try:
            span: trace.Span | None = getattr(context, _SPAN_ATTR, None) if context else None
            if span is None:
                return
            rowcount = getattr(cursor, "rowcount", -1) or 0
            span.set_attribute("db.rows_affected", rowcount)
            span.set_status(Status(StatusCode.OK))
            span.end()
        except Exception:
            _log.debug("sql_tracer.after_failed", exc_info=True)

    @event.listens_for(sync_engine, "handle_error")
    def _error(exception_context: Any) -> None:
        try:
            exec_ctx = getattr(exception_context, "execution_context", None)
            span: trace.Span | None = getattr(exec_ctx, _SPAN_ATTR, None) if exec_ctx else None
            if span is None:
                return
            original = getattr(exception_context, "original_exception", None)
            msg = str(original) if original else "unknown SQL error"
            span.set_status(Status(StatusCode.ERROR, msg))
            span.record_exception(original) if original else None
            span.end()
        except Exception:
            _log.debug("sql_tracer.error_handler_failed", exc_info=True)


def instrument_sql_database(db: Any) -> None:
    """Convenience: instrument both read and write engines of a SQLDatabaseImpl.

    Skips duplicate instrumentation when read_engine == write_engine.
    """
    try:
        read = db.read_engine()
        write = db.write_engine()
        instrument_engine(read)
        if write is not read:
            instrument_engine(write)
        _log.debug("sql_tracer.instrumented")
    except Exception:
        _log.warning("sql_tracer.instrument_failed", exc_info=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dialect_to_system(dialect_name: str) -> str:
    """Map SQLAlchemy dialect name to OTel db.system semantic convention."""
    _MAP = {
        "postgresql": "postgresql",
        "mysql": "mysql",
        "sqlite": "sqlite",
        "oracle": "oracle",
        "mssql": "mssql",
    }
    return _MAP.get(dialect_name.lower(), dialect_name or "other_sql")


def _extract_operation(statement: str) -> str:
    """Extract the SQL operation keyword from the first word of the statement."""
    first = statement.lstrip().split(None, 1)
    return first[0].upper() if first else "SQL"
