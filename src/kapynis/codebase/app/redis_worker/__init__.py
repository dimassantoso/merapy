"""Redis pub/sub subscriber worker. Mirrors candi's ``redis_worker``."""

from kapynis.codebase.app.redis_worker.worker import RedisWorker

__all__ = ["RedisWorker"]
