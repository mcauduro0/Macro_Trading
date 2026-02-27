"""Pydantic-settings configuration for the Macro Trading system.

Loads all service connection parameters from .env file with sensible
defaults for local development. Computed fields produce fully-formed
connection URLs for each service.
"""

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    # Project
    project_name: str = "Macro Trading"
    debug: bool = False

    # TimescaleDB / PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "macro_trading"
    postgres_user: str = "macro_user"
    postgres_password: str = ""

    # SQLAlchemy pool settings
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_pre_ping: bool = True
    db_sslmode: str = "prefer"  # Set to "require" in production

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    redis_max_connections: int = 50

    # MongoDB
    mongo_host: str = "localhost"
    mongo_port: int = 27017
    mongo_user: str = "macro_user"
    mongo_password: str = ""
    mongo_db: str = "macro_trading"

    # MinIO
    minio_host: str = "localhost"
    minio_port: int = 9000
    minio_access_key: str = "minio_user"
    minio_secret_key: str = ""
    minio_bucket: str = "macro-data"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"

    # API Keys (external data sources)
    fred_api_key: str = ""
    anthropic_api_key: str = ""

    # CORS
    allowed_origins: str = ""  # Comma-separated extra CORS origins

    # JWT Authentication
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60

    @computed_field
    @property
    def async_database_url(self) -> str:
        """Async connection string for asyncpg."""
        base = (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
        if self.db_sslmode and self.db_sslmode != "disable":
            return f"{base}?ssl={self.db_sslmode}"
        return base

    @computed_field
    @property
    def sync_database_url(self) -> str:
        """Sync connection string for psycopg2 (used by Alembic)."""
        base = (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
        if self.db_sslmode and self.db_sslmode != "disable":
            return f"{base}?sslmode={self.db_sslmode}"
        return base

    @computed_field
    @property
    def redis_url(self) -> str:
        """Redis connection URL."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @computed_field
    @property
    def mongo_url(self) -> str:
        """MongoDB connection URL."""
        return (
            f"mongodb://{self.mongo_user}:{self.mongo_password}"
            f"@{self.mongo_host}:{self.mongo_port}/{self.mongo_db}"
            f"?authSource=admin"
        )


# Singleton instance
settings = Settings()
