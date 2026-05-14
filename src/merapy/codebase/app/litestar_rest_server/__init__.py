"""Litestar-based REST adapter — alternative to the FastAPI adapter.

Selected via ``REST_FRAMEWORK=litestar`` env var.
"""

from merapy.codebase.app.litestar_rest_server.route_wrapper import LitestarRouteWrapper
from merapy.codebase.app.litestar_rest_server.server import LitestarRESTServer

__all__ = ["LitestarRESTServer", "LitestarRouteWrapper"]
