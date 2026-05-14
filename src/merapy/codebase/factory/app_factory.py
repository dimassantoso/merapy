from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class AppServerFactory(Protocol):
    """One concurrent server / worker in the running process.

    ``serve()`` blocks until the server is told to stop; ``shutdown()`` is
    invoked with a deadline by the orchestrator. ``name`` is used in logs.
    """

    @property
    def name(self) -> str: ...

    async def serve(self) -> None: ...

    async def shutdown(self) -> None: ...
