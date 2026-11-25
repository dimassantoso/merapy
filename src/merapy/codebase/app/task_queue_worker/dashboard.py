"""Task Queue Worker Dashboard adapter backed by standalone ``merapy-taskqueue``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from merapy_taskqueue.dashboard import (
    AddJobInputResolver,
    FilterMutateJobInputResolver,
    GetAllJobInputResolver,
    JobListResolver,
    JobResolver,
    MetaTaskResolver,
    MetaType,
    TaskDetailResolver,
    TaskListResolver,
    TaskResolver,
    WorkerStatsResolver,
    build_schema,
)
from merapy_taskqueue.dashboard import (
    TaskQueueDashboard as _StandaloneDashboard,
)
from merapy_taskqueue.dashboard import (
    find_static_dir as _standalone_find_static_dir,
)
from merapy_taskqueue.store.memory import MemoryJobStore
from merapy_taskqueue.store.sql import SQLJobStore
from merapy_taskqueue.types import DashboardConfig
from merapy_taskqueue.worker import TaskQueue


def _find_static_dir() -> Path | None:
    """Locate static dashboard assets (bundled in merapy or merapy_taskqueue)."""
    local_dir = Path(__file__).parent / "dashboard_static"
    if local_dir.is_dir() and (local_dir / "index.html").is_file():
        return local_dir.resolve()
    return _standalone_find_static_dir()


def _merapy_dashboard_config(port: int) -> DashboardConfig:
    from merapy import __version__ as merapy_version  # noqa: PLC0415
    from merapy.config.env import get_env  # noqa: PLC0415

    env = get_env()
    static_dir = _find_static_dir()
    return DashboardConfig(
        port=port,
        service_name=env.service_name,
        service_version=env.app_version,
        framework_version=merapy_version,
        build_number=env.build_number,
        git_commit=env.git_commit,
        build_date=env.build_date,
        static_dir=str(static_dir) if static_dir is not None else None,
    )


def _adapt_worker_to_queue(worker: Any, port: int) -> TaskQueue:
    if isinstance(worker, TaskQueue):
        return worker
    inner = getattr(worker, "_queue", None)
    if isinstance(inner, TaskQueue):
        return inner

    session_factory = getattr(worker, "_session_factory", None)
    store = SQLJobStore(session_factory) if session_factory is not None else MemoryJobStore()
    tq = TaskQueue(store=store, dashboard_enabled=False, dashboard_port=port)
    handlers = getattr(worker, "_handlers", None) or {}
    for task_name in handlers:

        async def _noop(_ctx: Any) -> None:
            return None

        tq.register(task_name, _noop, module_name=task_name)
    return tq


class TaskQueueDashboard(_StandaloneDashboard):
    """Backward-compatible wrapper around ``merapy_taskqueue.TaskQueueDashboard``."""

    def __init__(self, worker: Any, port: int = 8080) -> None:
        queue = _adapt_worker_to_queue(worker, port)
        config = _merapy_dashboard_config(port)
        super().__init__(queue, config=config, port=port)


__all__ = [
    "AddJobInputResolver",
    "FilterMutateJobInputResolver",
    "GetAllJobInputResolver",
    "JobListResolver",
    "JobResolver",
    "MetaTaskResolver",
    "MetaType",
    "TaskDetailResolver",
    "TaskListResolver",
    "TaskQueueDashboard",
    "TaskResolver",
    "WorkerStatsResolver",
    "_find_static_dir",
    "build_schema",
]
