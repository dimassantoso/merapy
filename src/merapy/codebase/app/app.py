"""Top-level orchestrator.

Starts every :class:`AppServerFactory` as an asyncio task. On SIGINT /
SIGTERM, calls ``shutdown()`` on each with a hard timeout (default 60s)
before cancelling outstanding tasks.
"""

from __future__ import annotations

import asyncio
import signal
import sys
from typing import TYPE_CHECKING

from merapy.logger import get_logger

if TYPE_CHECKING:
    from merapy.codebase.factory.service_factory import ServiceFactory

logger = get_logger(__name__)

_SHUTDOWN_TIMEOUT = 60.0


class App:
    """Wraps a :class:`ServiceFactory` and runs all its registered apps."""

    __slots__ = ("_service", "_stop_event")

    def __init__(self, service: "ServiceFactory") -> None:
        self._service = service
        self._stop_event = asyncio.Event()

    async def run(self) -> None:
        apps = self._service.applications()
        if not apps:
            logger.warning("app.no_servers")
            return

        loop = asyncio.get_running_loop()
        signals_attached: list[signal.Signals] = []
        # Windows lacks loop.add_signal_handler — fall back to default SIGINT only.
        if sys.platform != "win32":
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, self._stop_event.set)
                    signals_attached.append(sig)
                except NotImplementedError:
                    pass

        logger.info("app.starting", servers=[a.name for a in apps])

        async def supervise(server: object) -> None:
            try:
                await server.serve()  # type: ignore[attr-defined]
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("app.server_crashed", server=getattr(server, "name", "?"))
                self._stop_event.set()

        tasks = [
            asyncio.create_task(supervise(a), name=getattr(a, "name", repr(a)))
            for a in apps
        ]

        try:
            await self._stop_event.wait()
        finally:
            logger.info("app.stopping")
            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        *(a.shutdown() for a in apps), return_exceptions=True
                    ),
                    timeout=_SHUTDOWN_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.error("app.shutdown_timeout")

            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

            for sig in signals_attached:
                try:
                    loop.remove_signal_handler(sig)
                except Exception:
                    pass
            logger.info("app.stopped")

    def request_shutdown(self) -> None:
        """Trigger shutdown programmatically. Useful in tests."""
        self._stop_event.set()
