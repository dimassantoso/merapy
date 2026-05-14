"""Authentication / authorization middleware.

Mirrors candi's ``middleware/`` package. The :class:`MiddlewareImpl` class
composes pluggable validators (token, basic auth, ACL) and exposes guards
that fit FastAPI's ``Depends`` / Litestar's guard model.
"""

from merapy.middleware.base import MiddlewareBuilder, MiddlewareImpl

__all__ = ["MiddlewareBuilder", "MiddlewareImpl"]
