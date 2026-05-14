"""FastAPI-based REST server. Default ``RESTRouter`` adapter."""

from merapy.codebase.app.rest_server.route_wrapper import FastAPIRouteWrapper
from merapy.codebase.app.rest_server.server import RESTServer

__all__ = ["FastAPIRouteWrapper", "RESTServer"]
