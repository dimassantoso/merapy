"""Public Protocols used across kapynis.

Mirrors the ``codebase/interfaces/`` package in candi. Every cross-cutting
contract lives here so module code never depends on a concrete implementation.
"""

from merapy.codebase.interfaces.broker import Broker, Publisher
from merapy.codebase.interfaces.cache import Cache
from merapy.codebase.interfaces.closer import Closer
from merapy.codebase.interfaces.database import MongoDatabase, RedisPool, SQLDatabase
from merapy.codebase.interfaces.handlers import (
    GraphQLHandler,
    GRPCHandler,
    RESTHandler,
    ServerHandler,
    WorkerHandler,
)
from merapy.codebase.interfaces.locker import Locker
from merapy.codebase.interfaces.middleware import (
    ACLPermissionChecker,
    BasicAuthValidator,
    Middleware,
    TokenValidator,
)
from merapy.codebase.interfaces.rest_router import RESTRouter, RouteHandler
from merapy.codebase.interfaces.rsa_key import RSAKey
from merapy.codebase.interfaces.validator import Validator

__all__ = [
    "ACLPermissionChecker",
    "BasicAuthValidator",
    "Broker",
    "Cache",
    "Closer",
    "GraphQLHandler",
    "GRPCHandler",
    "Locker",
    "Middleware",
    "MongoDatabase",
    "Publisher",
    "RESTHandler",
    "RESTRouter",
    "RSAKey",
    "RedisPool",
    "RouteHandler",
    "SQLDatabase",
    "ServerHandler",
    "TokenValidator",
    "Validator",
    "WorkerHandler",
]
