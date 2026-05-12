"""Environment variable schema. Mirrors candi's ``config/env/environment.go``.

All boot decisions are env-driven: which servers run, which workers run,
where the databases are. The generated service extends this with its own
``Environment`` subclass (see ``pkg/shared/environment.py`` in the template).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class KafkaEnv(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KAFKA_", extra="ignore")

    brokers: list[str] = Field(default_factory=list)
    client_id: str = ""
    consumer_group: str = ""
    client_version: str = ""


class RabbitMQEnv(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RABBITMQ_", extra="ignore")

    broker: str = ""
    consumer_group: str = ""
    exchange_name: str = ""


class Env(BaseSettings):
    """Top-level env. Read once at boot from ``.env`` + process env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Service identity
    service_name: str = Field(default="kapynis-service", alias="SERVICE_NAME")
    environment: Literal["development", "staging", "production"] = Field(
        default="development", alias="ENVIRONMENT"
    )
    debug_mode: bool = Field(default=True, alias="DEBUG_MODE")
    load_config_timeout: float = Field(default=30.0, alias="LOAD_CONFIG_TIMEOUT")

    # Server toggles (mirrors candi USE_REST / USE_GRPC / USE_GRAPHQL)
    use_rest: bool = Field(default=True, alias="USE_REST")
    use_grpc: bool = Field(default=False, alias="USE_GRPC")
    use_graphql: bool = Field(default=False, alias="USE_GRAPHQL")

    # Worker toggles
    use_kafka_consumer: bool = Field(default=False, alias="USE_KAFKA_CONSUMER")
    use_cron_scheduler: bool = Field(default=False, alias="USE_CRON_SCHEDULER")
    use_redis_subscriber: bool = Field(default=False, alias="USE_REDIS_SUBSCRIBER")
    use_task_queue_worker: bool = Field(default=False, alias="USE_TASK_QUEUE_WORKER")
    use_postgres_listener: bool = Field(default=False, alias="USE_POSTGRES_LISTENER")
    use_rabbitmq_worker: bool = Field(default=False, alias="USE_RABBITMQ_WORKER")

    # REST framework selection (FastAPI default, Litestar via env)
    rest_framework: Literal["fastapi", "litestar"] = Field(
        default="fastapi", alias="REST_FRAMEWORK"
    )

    # Ports
    http_port: int = Field(default=8000, alias="HTTP_PORT")
    grpc_port: int = Field(default=9000, alias="GRPC_PORT")
    http_root_path: str = Field(default="/", alias="HTTP_ROOT_PATH")

    # SQL
    sql_dsn_read: str | None = Field(default=None, alias="SQL_DSN_READ")
    sql_dsn_write: str | None = Field(default=None, alias="SQL_DSN_WRITE")
    sql_pool_size: int = Field(default=10, alias="SQL_POOL_SIZE")
    sql_max_overflow: int = Field(default=5, alias="SQL_MAX_OVERFLOW")
    sql_echo: bool = Field(default=False, alias="SQL_ECHO")

    # MongoDB
    mongo_dsn_read: str | None = Field(default=None, alias="MONGO_DSN_READ")
    mongo_dsn_write: str | None = Field(default=None, alias="MONGO_DSN_WRITE")
    mongo_db_name: str = Field(default="", alias="MONGO_DB_NAME")

    # Redis
    redis_dsn_read: str | None = Field(default=None, alias="REDIS_DSN_READ")
    redis_dsn_write: str | None = Field(default=None, alias="REDIS_DSN_WRITE")

    # CORS
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: ["*"], alias="CORS_ALLOW_ORIGINS"
    )
    cors_allow_methods: list[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        alias="CORS_ALLOW_METHODS",
    )
    cors_allow_headers: list[str] = Field(
        default_factory=lambda: ["*"], alias="CORS_ALLOW_HEADERS"
    )
    cors_allow_credentials: bool = Field(default=True, alias="CORS_ALLOW_CREDENTIALS")

    # Limits
    max_goroutines: int = Field(default=10, alias="MAX_GOROUTINES")
    """Per-worker concurrency cap (asyncio.Semaphore). Name kept for parity."""

    # Brokers (nested env vars via KafkaEnv / RabbitMQEnv)
    kafka: KafkaEnv = Field(default_factory=KafkaEnv)
    rabbitmq: RabbitMQEnv = Field(default_factory=RabbitMQEnv)


@lru_cache(maxsize=1)
def get_env() -> Env:
    """Process-wide singleton. Reads ``.env`` once on first call."""
    return Env()
