"""Postgres LISTEN / NOTIFY worker. Mirrors candi's ``postgres_worker``."""

from merapy.codebase.app.postgres_worker.worker import PostgresListenerWorker

__all__ = ["PostgresListenerWorker"]
