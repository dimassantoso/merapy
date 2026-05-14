"""Repository-layer helpers shipped by the framework.

The concrete ``RepoSQL`` / ``RepoMongo`` aggregators are *generated* in
``pkg/shared/repository/`` per service. The framework provides:

* :class:`SharedSingleton` — generic ``SetShared / GetShared`` mechanic.
* :func:`with_transaction` — contextvar-based transaction propagation.
* :class:`BaseSQLRepository` — base for module SQL repositories.
* :class:`BaseMongoRepository` — base for module Mongo repositories.
"""

from merapy.repository.base import BaseMongoRepository, BaseSQLRepository
from merapy.repository.transaction import (
    current_session,
    get_current_session,
    with_transaction,
)
from merapy.repository.uow import SharedSingleton

__all__ = [
    "BaseMongoRepository",
    "BaseSQLRepository",
    "SharedSingleton",
    "current_session",
    "get_current_session",
    "with_transaction",
]
