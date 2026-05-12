"""Litestar-based REST adapter — alternative to the FastAPI adapter.

Selected via ``REST_FRAMEWORK=litestar`` env var. Mirrors candi's
"echo default + fiber plugin" model.
"""

from kapynis.codebase.app.litestar_rest_server.route_wrapper import LitestarRouteWrapper
from kapynis.codebase.app.litestar_rest_server.server import LitestarRESTServer

__all__ = ["LitestarRESTServer", "LitestarRouteWrapper"]
