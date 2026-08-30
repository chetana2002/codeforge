import socket
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = (
        "postgresql+psycopg://codeforge:codeforge_dev_password@localhost:5432/codeforge"
    )
    redis_url: str = "redis://localhost:6379/0"

    docker_socket: str = "/var/run/docker.sock"
    execution_timeout_seconds: int = 10
    execution_memory_limit_mb: int = 128
    execution_cpu_limit: float = 0.5
    execution_pids_limit: int = 64

    consumer_group: str = "execution-workers"
    # Defaults to the container hostname so `docker compose up --scale worker=N`
    # gives each replica a distinct Redis Streams consumer identity for free.
    consumer_name: str = Field(default_factory=socket.gethostname)
    stream_key: str = "codeforge:executions"


@lru_cache
def get_worker_settings() -> WorkerSettings:
    return WorkerSettings()
