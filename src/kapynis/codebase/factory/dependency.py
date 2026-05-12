"""Dependency container — module-level singleton.

Mirrors candi's ``codebase/factory/dependency/dependency.go``. The container
holds every shared resource: DBs, cache, brokers, middleware, validator,
locker, RSA key, and a free-form ``extended`` bag.

Construction is via :class:`DependencyBuilder` (mirrors candi's Option
functor pattern). The result is stashed in a module-level ``_std_deps``
singleton so any code can pull deps from ``get_*()`` free functions —
matching candi's ``dependency.GetMiddleware()``-style access.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Self

from kapynis.codebase.interfaces import (
    Broker,
    Cache,
    Locker,
    Middleware,
    MongoDatabase,
    RedisPool,
    RSAKey,
    SQLDatabase,
    Validator,
)
from kapynis.codebase.types import Worker

_lock = threading.Lock()


@dataclass(slots=True)
class _Deps:
    sql_db: SQLDatabase | None = None
    mongo_db: MongoDatabase | None = None
    redis_pool: RedisPool | None = None
    brokers: dict[Worker, Broker] = field(default_factory=dict)
    middleware: Middleware | None = None
    validator: Validator | None = None
    locker: Locker | None = None
    rsa_key: RSAKey | None = None
    extended: dict[str, Any] = field(default_factory=dict)


_std_deps: _Deps = _Deps()
_initialized = False


class Dependency:
    """Public view over the module-level ``_std_deps`` singleton.

    Instances are interchangeable — they all read/write the same underlying
    state. The class form exists so generated services can pass ``deps``
    around without exposing the module globals directly.
    """

    __slots__ = ()

    # Accessors — return None if not wired yet.
    def sql_db(self) -> SQLDatabase | None:
        return _std_deps.sql_db

    def mongo_db(self) -> MongoDatabase | None:
        return _std_deps.mongo_db

    def redis_pool(self) -> RedisPool | None:
        return _std_deps.redis_pool

    def cache(self) -> Cache | None:
        return _std_deps.redis_pool.cache() if _std_deps.redis_pool else None

    def broker(self, worker_type: Worker) -> Broker | None:
        return _std_deps.brokers.get(worker_type)

    def brokers(self) -> dict[Worker, Broker]:
        return dict(_std_deps.brokers)

    def middleware(self) -> Middleware | None:
        return _std_deps.middleware

    def validator(self) -> Validator | None:
        return _std_deps.validator

    def locker(self) -> Locker | None:
        return _std_deps.locker

    def rsa_key(self) -> RSAKey | None:
        return _std_deps.rsa_key

    def extended(self, key: str) -> Any:
        return _std_deps.extended.get(key)

    # Late-binding setters (used by ``configs.load_service_configs`` after
    # the middleware / validator are constructed).
    def set_middleware(self, mw: Middleware) -> None:
        _std_deps.middleware = mw

    def set_validator(self, v: Validator) -> None:
        _std_deps.validator = v


class DependencyBuilder:
    """Fluent builder for the module-level singleton.

    Mirrors candi's ``InitDependency(opts...)``. Calling :meth:`build` twice
    is idempotent — the second call short-circuits, matching ``sync.Once``.
    """

    def __init__(self) -> None:
        self._draft = _Deps()

    def with_sql_db(self, db: SQLDatabase) -> Self:
        self._draft.sql_db = db
        return self

    def with_mongo_db(self, db: MongoDatabase) -> Self:
        self._draft.mongo_db = db
        return self

    def with_redis_pool(self, p: RedisPool) -> Self:
        self._draft.redis_pool = p
        return self

    def with_broker(self, worker_type: Worker, broker: Broker) -> Self:
        self._draft.brokers[worker_type] = broker
        return self

    def with_brokers(self, brokers: dict[Worker, Broker]) -> Self:
        self._draft.brokers.update(brokers)
        return self

    def with_middleware(self, mw: Middleware) -> Self:
        self._draft.middleware = mw
        return self

    def with_validator(self, v: Validator) -> Self:
        self._draft.validator = v
        return self

    def with_locker(self, lk: Locker) -> Self:
        self._draft.locker = lk
        return self

    def with_rsa_key(self, k: RSAKey) -> Self:
        self._draft.rsa_key = k
        return self

    def with_extended(self, key: str, value: Any) -> Self:
        self._draft.extended[key] = value
        return self

    def build(self) -> Dependency:
        global _initialized
        with _lock:
            if _initialized:
                return Dependency()
            _std_deps.sql_db = self._draft.sql_db or _std_deps.sql_db
            _std_deps.mongo_db = self._draft.mongo_db or _std_deps.mongo_db
            _std_deps.redis_pool = self._draft.redis_pool or _std_deps.redis_pool
            _std_deps.brokers.update(self._draft.brokers)
            _std_deps.middleware = self._draft.middleware or _std_deps.middleware
            _std_deps.validator = self._draft.validator or _std_deps.validator
            _std_deps.locker = self._draft.locker or _std_deps.locker
            _std_deps.rsa_key = self._draft.rsa_key or _std_deps.rsa_key
            _std_deps.extended.update(self._draft.extended)
            _initialized = True
        return Dependency()


# Free-function getters — mirror candi's ``dependency.GetMiddleware()`` style.


def get_dependency() -> Dependency:
    return Dependency()


def get_sql_db() -> SQLDatabase | None:
    return _std_deps.sql_db


def get_mongo_db() -> MongoDatabase | None:
    return _std_deps.mongo_db


def get_redis_pool() -> RedisPool | None:
    return _std_deps.redis_pool


def get_broker(worker_type: Worker) -> Broker | None:
    return _std_deps.brokers.get(worker_type)


def get_middleware() -> Middleware | None:
    return _std_deps.middleware


def get_validator() -> Validator | None:
    return _std_deps.validator


def get_locker() -> Locker | None:
    return _std_deps.locker


def reset_dependency_for_tests() -> None:
    """Reset the singleton — tests only.

    Without this, test ordering would matter. Production code never calls
    this.
    """
    global _initialized
    with _lock:
        _std_deps.sql_db = None
        _std_deps.mongo_db = None
        _std_deps.redis_pool = None
        _std_deps.brokers.clear()
        _std_deps.middleware = None
        _std_deps.validator = None
        _std_deps.locker = None
        _std_deps.rsa_key = None
        _std_deps.extended.clear()
        _initialized = False
