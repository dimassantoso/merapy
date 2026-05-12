"""Public Protocols used across kapynis.

Mirrors the ``codebase/interfaces/`` package in candi. Every cross-cutting
contract lives here so module code never depends on a concrete implementation.
"""

from kapynis.codebase.interfaces.broker import Broker, Publisher
from kapynis.codebase.interfaces.cache import Cache
from kapynis.codebase.interfaces.closer import Closer
from kapynis.codebase.interfaces.database import MongoDatabase, RedisPool, SQLDatabase
from kapynis.codebase.interfaces.handlers import (
    GraphQLHandler,
    GRPCHandler,
    RESTHandler,
    ServerHandler,
    WorkerHandler,
)
from kapynis.codebase.interfaces.locker import Locker
from kapynis.codebase.interfaces.middleware import (
    ACLPermissionChecker,
    BasicAuthValidator,
    Middleware,
    TokenValidator,
)
from kapynis.codebase.interfaces.rest_router import RESTRouter, RouteHandler
from kapynis.codebase.interfaces.rsa_key import RSAKey
from kapynis.codebase.interfaces.validator import Validator

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
