"""
Application and Database Configuration Module
Loads configuration from environment variables and .env file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from dotenv import load_dotenv

# Load variables from .env file if present
load_dotenv()


@dataclass(frozen=True)
class DatabaseConfig:
    """PostgreSQL connection and pooling configuration."""
    host: str
    port: int
    database: str
    user: str
    password: str
    pool_min_size: int
    pool_max_size: int
    pool_timeout: float
    connect_timeout: int = 5

    @classmethod
    def from_env(cls) -> DatabaseConfig:
        """Instantiate configuration from environment variables with validation."""
        host = os.getenv("DB_HOST", "localhost")
        database = os.getenv("DB_NAME", "campus_maintenance")
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD", "")

        try:
            port = int(os.getenv("DB_PORT", "5432"))
        except ValueError as err:
            raise ValueError(f"Invalid DB_PORT integer: {os.getenv('DB_PORT')}") from err

        try:
            pool_min_size = int(os.getenv("DB_POOL_MIN_SIZE", "1"))
            pool_max_size = int(os.getenv("DB_POOL_MAX_SIZE", "10"))
            pool_timeout = float(os.getenv("DB_POOL_TIMEOUT", "30.0"))
            connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))
        except ValueError as err:
            raise ValueError("Invalid connection pool parameter in environment variables") from err

        if pool_min_size < 1:
            raise ValueError("DB_POOL_MIN_SIZE must be at least 1")
        if pool_max_size < pool_min_size:
            raise ValueError("DB_POOL_MAX_SIZE must be greater than or equal to DB_POOL_MIN_SIZE")

        return cls(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            pool_min_size=pool_min_size,
            pool_max_size=pool_max_size,
            pool_timeout=pool_timeout,
            connect_timeout=connect_timeout,
        )

    def get_conninfo(self) -> str:
        """Build standard PostgreSQL connection string."""
        parts = [
            f"host={self.host}",
            f"port={self.port}",
            f"dbname={self.database}",
            f"user={self.user}",
            f"connect_timeout={self.connect_timeout}",
        ]
        if self.password:
            parts.append(f"password={self.password}")
        return " ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Return connection arguments dictionary for psycopg."""
        kwargs: dict[str, Any] = {
            "host": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": self.user,
            "connect_timeout": self.connect_timeout,
        }
        if self.password:
            kwargs["password"] = self.password
        return kwargs


@dataclass(frozen=True)
class AppConfig:
    """Global application configuration."""
    env: str
    log_level: str
    db: DatabaseConfig

    @classmethod
    def load(cls) -> AppConfig:
        """Load full application configuration."""
        env = os.getenv("APP_ENV", "development").lower()
        log_level = os.getenv("APP_LOG_LEVEL", "INFO").upper()
        db_config = DatabaseConfig.from_env()

        return cls(
            env=env,
            log_level=log_level,
            db=db_config,
        )


_config_instance: AppConfig | None = None


def get_config(reload: bool = False) -> AppConfig:
    """Return singleton application configuration instance."""
    global _config_instance
    if _config_instance is None or reload:
        _config_instance = AppConfig.load()
    return _config_instance
