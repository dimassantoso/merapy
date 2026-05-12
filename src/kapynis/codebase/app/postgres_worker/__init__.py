"""Postgres LISTEN / NOTIFY worker. Mirrors candi's ``postgres_worker``."""

from kapynis.codebase.app.postgres_worker.worker import PostgresListenerWorker

__all__ = ["PostgresListenerWorker"]
