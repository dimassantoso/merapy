"""RabbitMQ consumer worker. Mirrors candi's ``rabbitmq_worker``."""

from kapynis.codebase.app.rabbitmq_worker.worker import RabbitMQWorker

__all__ = ["RabbitMQWorker"]
