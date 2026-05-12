from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Closer(Protocol):
    """Anything that owns resources that must be released at shutdown.

    Mirrors candi's ``interfaces.Closer``. Returned by component constructors
    (DB pools, broker clients, lockers) so the bootstrap can defer cleanup.
    """

    async def close(self) -> None: ...
