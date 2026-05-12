"""Transaction propagation via :mod:`contextvars`.

Mirrors candi's ``RepoSQL.WithTransaction(ctx, fn)`` where the transaction
travels with ``context.Context``. In Python the natural carrier is a
``ContextVar`` — set when a transaction is opened, read by repositories
when they decide whether to start their own session.

Behavior:

* Top-level ``with_transaction(...)`` opens an :class:`AsyncSession`,
  begins a transaction, and stores the session in the contextvar.
* Nested calls inside the same async task **reuse the outer session**;
  commit/rollback decisions are made at the outermost level only.
* Repositories use :func:`get_current_session` to participate in the
  ambient transaction, or open their own short-lived session if none
  is active.

``asyncio.create_task`` does NOT inherit contextvar values by default —
if you spawn tasks inside a transaction, the new task will not see it.
This matches candi's behavior (goroutine = new context).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_session_ctx: ContextVar[AsyncSession | None] = ContextVar(
    "kapynis_sql_session", default=None
)


def get_current_session() -> AsyncSession | None:
    """Return the ambient :class:`AsyncSession`, or ``None`` outside a transaction."""
    return _session_ctx.get()


@asynccontextmanager
async def with_transaction(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Open or reuse a transaction.

    Example::

        async def update_balance(user_id, delta):
            async with with_transaction(deps.sql_db().session_factory()) as session:
                # all repository calls inside use this session
                await user_repo.deduct(user_id, delta)
                await audit_repo.log(user_id, delta)
            # transaction commits on exit; rolls back on exception
    """
    existing = _session_ctx.get()
    if existing is not None:
        yield existing
        return

    async with session_factory() as session:
        token = _session_ctx.set(session)
        try:
            async with session.begin():
                yield session
        finally:
            _session_ctx.reset(token)


@asynccontextmanager
async def current_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield the ambient session, or open a one-shot session if none is active.

    Used by repositories whose queries should NOT start a transaction on
    their own — they participate in one only if the caller opened it.
    """
    existing = _session_ctx.get()
    if existing is not None:
        yield existing
        return
    async with session_factory() as session:
        yield session
