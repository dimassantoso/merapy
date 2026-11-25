"""Pluggable storage backends for ``merapy-taskqueue``."""

from __future__ import annotations

from merapy_taskqueue.store.base import JobStore
from merapy_taskqueue.store.memory import MemoryJobStore

__all__ = ["JobStore", "MemoryJobStore"]
