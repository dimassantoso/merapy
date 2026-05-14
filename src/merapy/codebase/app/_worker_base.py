"""Shared scaffolding for worker :class:`AppServerFactory` implementations.

Each transport (Cron, Kafka, RabbitMQ, Redis sub, Postgres listen, Task queue)
has its own bookkeeping, but the discovery pattern is identical: iterate
``service.modules()``, ask each for a :class:`WorkerHandler` of the relevant
``Worker`` type, then call ``mount_handlers`` on a fresh group.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from merapy.codebase.types import Worker, WorkerHandlerEntry, WorkerHandlerGroup

if TYPE_CHECKING:
    from merapy.codebase.factory.service_factory import ServiceFactory


def collect_handlers(
    service: "ServiceFactory", worker_type: Worker
) -> list[tuple[str, WorkerHandlerEntry]]:
    """Return ``(module_name, entry)`` pairs for every handler registered
    for ``worker_type`` across all modules.
    """
    out: list[tuple[str, WorkerHandlerEntry]] = []
    for module in service.modules():
        wh = module.worker_handler(worker_type)
        if wh is None:
            continue
        group = WorkerHandlerGroup()
        wh.mount_handlers(group)
        for entry in group.handlers:
            out.append((module.name, entry))
    return out
