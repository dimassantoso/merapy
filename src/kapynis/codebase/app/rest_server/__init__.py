"""FastAPI-based REST server. Default ``RESTRouter`` adapter."""

from kapynis.codebase.app.rest_server.route_wrapper import FastAPIRouteWrapper
from kapynis.codebase.app.rest_server.server import RESTServer

__all__ = ["FastAPIRouteWrapper", "RESTServer"]
