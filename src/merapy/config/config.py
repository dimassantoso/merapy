"""Boot lifecycle. Mirrors candi's ``config/config.go``.

Owns the load → connect → use → close sequence. Holds the list of
``Closer`` instances returned by component constructors so that
``app.App.run()`` can shut them down deterministically at exit.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from merapy.codebase.interfaces import Closer
from merapy.config.env import Env, get_env
from merapy.logger import get_logger

logger = get_logger(__name__)

LoadFunc = Callable[["Config"], Awaitable[list[Closer]]]


class Config:
    """Holds the parsed env and the registered closers.

    The generated service builds a ``Config``, calls
    :meth:`load`, then hands it to ``Service(cfg)``. Closers accumulated
    during ``load`` are released by :meth:`shutdown` in reverse order.
    """

    __slots__ = ("env", "_closers", "_loaded")

    def __init__(self, env: Env | None = None) -> None:
        self.env: Env = env or get_env()
        self._closers: list[Closer] = []
        self._loaded = False

    async def load(self, load_func: LoadFunc) -> None:
        """Run ``load_func`` under the configured timeout, store closers."""
        if self._loaded:
            return
        try:
            closers = await asyncio.wait_for(
                load_func(self), timeout=self.env.load_config_timeout
            )
        except asyncio.TimeoutError as e:
            raise RuntimeError(
                f"config load timed out after {self.env.load_config_timeout}s"
            ) from e
        self._closers.extend(closers)
        self._loaded = True
        logger.info("config.loaded", closers=len(self._closers))

    async def shutdown(self) -> None:
        for closer in reversed(self._closers):
            try:
                await closer.close()
            except Exception:
                logger.exception("config.closer_failed", closer=type(closer).__name__)
        self._closers.clear()
        self._loaded = False


def load_config(env: Env | None = None) -> Config:
    return Config(env)
