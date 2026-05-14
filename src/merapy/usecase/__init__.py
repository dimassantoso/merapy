"""Usecase-layer scaffolding.

The framework provides:

* :class:`BaseUsecase` — convenience base with all the deps wired.
* :class:`UsecaseSingleton` — the shared UOW holder (``set_shared_usecase`` /
  ``get_shared_usecase`` + ``set_common_usecase``).

The concrete ``Usecase`` aggregator and the cross-module ``Common`` bridge
are generated per service in ``pkg/shared/usecase/`` (see the CLI templates).
"""

from merapy.usecase.base import BaseUsecase
from merapy.usecase.singleton import (
    CommonSingleton,
    UsecaseSingleton,
    common_usecase,
    set_common_usecase,
)

__all__ = [
    "BaseUsecase",
    "CommonSingleton",
    "UsecaseSingleton",
    "common_usecase",
    "set_common_usecase",
]
