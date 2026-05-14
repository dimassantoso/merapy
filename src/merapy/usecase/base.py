"""Base for module usecases.

Mirrors candi's per-module ``XUsecaseImpl`` struct. Holds the common deps:
SQL/Mongo repositories (via the shared UOW), cache, locker, publisher map,
and a late-bound reference to the cross-module ``common.Usecase`` bridge.

Generated usecases subclass this and implement the module-specific
interface; the constructor returns ``(usecase, set_shared_uc_func)`` so the
UOW init can wire the cross-module reference later.
"""

from __future__ import annotations

from typing import Any, Callable

from merapy.codebase.factory.dependency import Dependency
from merapy.codebase.interfaces.broker import Publisher
from merapy.codebase.interfaces.cache import Cache
from merapy.codebase.interfaces.locker import Locker
from merapy.codebase.types import Worker


class BaseUsecase:
    """Common attributes available to every module usecase."""

    __slots__ = (
        "_deps",
        "_cache",
        "_locker",
        "_publishers",
        "_shared_usecase",
        "_repo_sql",
        "_repo_mongo",
    )

    def __init__(
        self,
        deps: Dependency,
        *,
        repo_sql: Any = None,
        repo_mongo: Any = None,
    ) -> None:
        self._deps = deps
        self._cache: Cache | None = deps.cache()
        self._locker: Locker | None = deps.locker()
        self._publishers: dict[Worker, Publisher] = {
            wt: b.publisher() for wt, b in deps.brokers().items()
        }
        self._shared_usecase: Any = None
        self._repo_sql = repo_sql
        self._repo_mongo = repo_mongo

    # Late binding for the cross-module bridge.
    def _set_shared_usecase(self, shared: Any) -> None:
        self._shared_usecase = shared

    def shared_usecase(self) -> Any:
        if self._shared_usecase is None:
            raise RuntimeError("shared usecase bridge not wired yet")
        return self._shared_usecase

    @property
    def deps(self) -> Dependency:
        return self._deps

    @property
    def cache(self) -> Cache | None:
        return self._cache

    @property
    def locker(self) -> Locker | None:
        return self._locker

    def publisher(self, worker_type: Worker) -> Publisher | None:
        return self._publishers.get(worker_type)


UsecaseConstructor = Callable[[Dependency], tuple["BaseUsecase", Callable[[Any], None]]]
"""Signature mirroring candi's ``NewXUsecase(deps) (X, func(shared))``.

The second return value is invoked by the UOW init with the cross-module
``common.Usecase`` bridge so the new usecase can call sibling modules
without circular imports.
"""
