"""
Database Connection and Session Management Module
Manages psycopg connection pooling, transactions, and connectivity health checks.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Generator
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import DatabaseConfig, get_config
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """Manages PostgreSQL connection pooling and lifecycle."""

    def __init__(self, config: DatabaseConfig | None = None) -> None:
        self.config = config or get_config().db
        self._pool: ConnectionPool | None = None

    def initialize_pool(self) -> None:
        """Create and open the connection pool if not already initialized."""
        if self._pool is None or self._pool.closed:
            logger.info(
                "Initializing PostgreSQL connection pool (%s:%s/%s, min=%s, max=%s)",
                self.config.host,
                self.config.port,
                self.config.database,
                self.config.pool_min_size,
                self.config.pool_max_size,
            )
            self._pool = ConnectionPool(
                conninfo=self.config.get_conninfo(),
                min_size=self.config.pool_min_size,
                max_size=self.config.pool_max_size,
                timeout=self.config.pool_timeout,
                kwargs={"row_factory": dict_row},
                open=False,
            )
            self._pool.open(wait=True, timeout=float(self.config.connect_timeout))
            logger.info("Connection pool successfully opened")

    def close_pool(self) -> None:
        """Close all connections in the pool."""
        if self._pool is not None:
            try:
                if not self._pool.closed:
                    logger.info("Closing PostgreSQL connection pool")
                    self._pool.close()
            finally:
                self._pool = None

    @contextmanager
    def get_connection(self) -> Generator[psycopg.Connection, None, None]:
        """Borrow a connection from the pool and return it upon context exit."""
        self.initialize_pool()
        assert self._pool is not None
        with self._pool.connection() as conn:
            yield conn

    @contextmanager
    def transaction(self) -> Generator[psycopg.Connection, None, None]:
        """Borrow a connection and wrap operations within an atomic transaction."""
        self.initialize_pool()
        assert self._pool is not None
        with self._pool.connection() as conn:
            with conn.transaction():
                yield conn

    def check_health(self) -> dict[str, Any]:
        """
        Execute diagnostic query to verify database connectivity,
        server version, database identity, and public table counts.
        """
        start_time = time.perf_counter()
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Verify connectivity and retrieve system diagnostics
                    cur.execute(
                        """
                        SELECT 
                            current_database() AS db_name,
                            current_user AS db_user,
                            version() AS pg_version,
                            (SELECT count(*) FROM information_schema.tables 
                             WHERE table_schema = 'public' AND table_type = 'BASE TABLE') AS table_count
                        """
                    )
                    row = cur.fetchone()
                    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

                    if row is None:
                        return {
                            "status": "unhealthy",
                            "error": "No diagnostic record returned from database",
                        }

                    return {
                        "status": "healthy",
                        "database": row["db_name"],
                        "user": row["db_user"],
                        "server_version": row["pg_version"].split(",")[0],
                        "public_tables_count": row["table_count"],
                        "latency_ms": duration_ms,
                    }
        except Exception as err:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error("Database health check failed: %s", err)
            return {
                "status": "unhealthy",
                "error": str(err),
                "latency_ms": duration_ms,
            }


_db_manager_instance: DatabaseManager | None = None


def get_db_manager() -> DatabaseManager:
    """Return singleton database manager instance."""
    global _db_manager_instance
    if _db_manager_instance is None:
        _db_manager_instance = DatabaseManager()
    return _db_manager_instance


@contextmanager
def get_connection() -> Generator[psycopg.Connection, None, None]:
    """Convenience context manager to borrow a pooled database connection."""
    manager = get_db_manager()
    with manager.get_connection() as conn:
        yield conn


def check_db_health() -> dict[str, Any]:
    """Convenience function to run a database health check."""
    return get_db_manager().check_health()


def _cleanup_global_pool() -> None:
    """Atexit hook to cleanly close pool threads upon process termination."""
    global _db_manager_instance
    if _db_manager_instance is not None:
        _db_manager_instance.close_pool()


import atexit

atexit.register(_cleanup_global_pool)
