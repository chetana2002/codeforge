from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, sourced from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"

    # Database
    database_url: str = (
        "postgresql+psycopg://codeforge:codeforge_dev_password@localhost:5432/codeforge"
    )

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    secret_key: str = "dev-only-secret-change-me"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    cookie_secure: bool = False
    cookie_domain: str = "localhost"

    # CORS
    cors_origins: str = "http://localhost:3000"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Execution sandbox
    execution_timeout_seconds: int = 10
    execution_memory_limit_mb: int = 128
    execution_cpu_limit: float = 0.5
    execution_pids_limit: int = 64
    docker_socket: str = "/var/run/docker.sock"

    # Rate limiting
    rate_limit_login_per_minute: int = 5
    rate_limit_execution_per_minute: int = 20
    rate_limit_project_create_per_minute: int = 20

    # Observability
    otel_exporter_otlp_endpoint: str = ""

    # SSE
    execution_stream_max_seconds: int = 120
    execution_stream_keepalive_seconds: float = 5.0

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
