"""Generic singleton wrapper for the ``Set/GetShared`` UOW pattern.

Each generated service wraps its ``RepoSQL`` / ``RepoMongo`` / ``Usecase``
aggregators with one of these so the singleton lifecycle is consistent and
idempotent (mirrors Go's ``sync.Once``).
"""

from __future__ import annotations

import threading
from typing import Generic, TypeVar

T = TypeVar("T")


class SharedSingleton(Generic[T]):
    """Idempotent process-wide singleton holder.

    First :meth:`set` wins; subsequent calls are no-ops. :meth:`get` raises
    if accessed before initialization — surfaces wiring bugs early.
    """

    __slots__ = ("_instance", "_initialized", "_lock", "_name")

    def __init__(self, name: str = "shared") -> None:
        self._instance: T | None = None
        self._initialized = False
        self._lock = threading.Lock()
        self._name = name

    def set(self, instance: T) -> None:
        with self._lock:
            if self._initialized:
                return
            self._instance = instance
            self._initialized = True

    def get(self) -> T:
        if self._instance is None:
            raise RuntimeError(f"shared {self._name} accessed before initialization")
        return self._instance

    @property
    def initialized(self) -> bool:
        return self._initialized

    def reset_for_tests(self) -> None:
        with self._lock:
            self._instance = None
            self._initialized = False
