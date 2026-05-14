"""App orchestration + server / worker implementations.

Mirrors candi's ``codebase/app/`` package. The top-level :class:`App` runs
every registered :class:`AppServerFactory` concurrently and coordinates
graceful shutdown on SIGINT / SIGTERM.
"""

from merapy.codebase.app.app import App

__all__ = ["App"]
