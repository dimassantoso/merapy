"""Cron-driven scheduler. Mirrors candi's ``codebase/app/cron_worker``.

Each module registers cron handlers via its worker handler::

    def mount_handlers(self, group):
        group.add("0 * * * *", self._hourly_summary)
        group.add("@every 30s", self._poll_inbox)

Supported pattern forms:

* Standard 5-field cron expression (``min hour dom mon dow``).
* ``@every <duration>`` where duration is ``Ns`` / ``Nm`` / ``Nh`` / ``Nd``.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from croniter import croniter

from kapynis.codebase.app._worker_base import collect_handlers
from kapynis.codebase.types import EventContext, Worker, WorkerHandlerEntry
from kapynis.logger import get_logger
from kapynis.tracer import start_trace

if TYPE_CHECKING:
    from kapynis.codebase.factory.service_factory import ServiceFactory

logger = get_logger(__name__)

_EVERY_RE = re.compile(r"^@every\s+(\d+)([smhd])$")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def _next_delay_seconds(pattern: str, now: datetime) -> float:
    """Compute seconds until the next firing of ``pattern``."""
    m = _EVERY_RE.match(pattern.strip())
    if m:
        return int(m.group(1)) * _UNIT_SECONDS[m.group(2)]
    cron = croniter(pattern, now)
    next_at: datetime = cron.get_next(datetime)
    delta = (next_at - now).total_seconds()
    return max(delta, 0.1)


class CronWorker:
    name = "cron"

    __slots__ = ("_service", "_stop", "_tasks", "_semaphore")

    def __init__(self, service: "ServiceFactory") -> None:
        self._service = service
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []
        self._semaphore: asyncio.Semaphore | None = None

    async def serve(self) -> None:
        env = self._service.config().env
        self._semaphore = asyncio.Semaphore(env.max_workers)
        entries = collect_handlers(self._service, Worker.SCHEDULER)
        if not entries:
            logger.info("cron.no_handlers")
            await self._stop.wait()
            return

        logger.info(
            "cron.starting",
            handlers=[(m, e.pattern) for m, e in entries],
        )
        self._tasks = [
            asyncio.create_task(self._run_loop(module, entry), name=f"cron:{module}:{entry.pattern}")
            for module, entry in entries
        ]
        await self._stop.wait()

    async def _run_loop(self, module: str, entry: WorkerHandlerEntry) -> None:
        assert self._semaphore is not None
        while not self._stop.is_set():
            now = datetime.now(tz=timezone.utc)
            try:
                delay = _next_delay_seconds(entry.pattern, now)
            except Exception:
                logger.exception("cron.invalid_pattern", module=module, pattern=entry.pattern)
                return

            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
                return  # stop signalled during wait
            except asyncio.TimeoutError:
                pass

            async with self._semaphore:
                ctx = EventContext(
                    worker_type=Worker.SCHEDULER.value,
                    handler_route=entry.pattern,
                    key=module,
                )
                if entry.disable_trace:
                    await self._invoke(module, entry, ctx)
                else:
                    async with start_trace(f"Cron:{module}:{entry.pattern}") as span:
                        span.set_attribute("cron.pattern", entry.pattern)
                        span.set_attribute("module", module)
                        await self._invoke(module, entry, ctx)

    async def _invoke(self, module: str, entry: WorkerHandlerEntry, ctx: EventContext) -> None:
        try:
            await entry.handler(ctx)
        except Exception:
            logger.exception("cron.handler_failed", module=module, pattern=entry.pattern)

    async def shutdown(self) -> None:
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
