"""Shared usecase singletons.

Mirrors candi's:

* ``SetSharedUsecase(deps)`` / ``GetSharedUsecase()`` — single UOW aggregating
  every module's usecase implementation.
* ``common.SetCommonUsecase(uc)`` / ``common.GetCommonUsecase()`` — bridge so
  module A can call module B's usecase without an import cycle.

The framework ships the *plumbing*; the generated ``pkg/shared/usecase/usecase.py``
defines the concrete ``Usecase`` aggregator class with one accessor per module.
"""

from __future__ import annotations

import threading
from typing import Any, Callable

from kapynis.repository.uow import SharedSingleton


class UsecaseSingleton(SharedSingleton[Any]):
    """Holds the shared :class:`Usecase` UOW aggregator instance.

    Generated code typically wraps it::

        _shared = UsecaseSingleton(name="usecase")

        def set_shared_usecase(deps): _shared.set(_build(deps))
        def get_shared_usecase(): return _shared.get()
    """

    def __init__(self) -> None:
        super().__init__(name="usecase")


class CommonSingleton(SharedSingleton[Any]):
    """Holds the cross-module ``common.Usecase`` bridge."""

    def __init__(self) -> None:
        super().__init__(name="common-usecase")


# Process-wide common bridge — used by ``set_common_usecase`` / ``common_usecase``.
_common: CommonSingleton = CommonSingleton()
_lock = threading.Lock()


def set_common_usecase(uc: Any) -> None:
    """Register the cross-module bridge once during boot.

    Idempotent — first call wins.
    """
    _common.set(uc)


def common_usecase() -> Any:
    """Retrieve the cross-module bridge. Raises if not yet wired."""
    return _common.get()


# Hook for tests.
def reset_common_usecase_for_tests() -> None:
    with _lock:
        _common.reset_for_tests()


WireCallback = Callable[[Any], None]
"""``func(shared_uc) -> None`` registered by each module's
``New<Module>Usecase`` constructor (second tuple element); invoked by the
UOW init after the bridge is built so modules can call each other.
"""
