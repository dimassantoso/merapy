"""RabbitMQ consumer worker. Mirrors candi's ``rabbitmq_worker``."""

from merapy.codebase.app.rabbitmq_worker.worker import RabbitMQWorker

__all__ = ["RabbitMQWorker"]
