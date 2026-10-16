"""
Integration Tests for Database Connectivity, Health-Checks, and Failure Handling
"""

from __future__ import annotations

import pytest
from app.config import DatabaseConfig
from app.db import DatabaseManager, check_db_health, get_connection
from app.repositories.base import BaseRepository


def test_database_connection_and_simple_query():
    """Verify active connection to PostgreSQL can execute simple read query."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS num, current_database() AS db")
            row = cur.fetchone()
            assert row is not None
            assert row["num"] == 1
            assert row["db"] == "campus_maintenance"


def test_database_health_check_success():
    """Verify health check returns healthy status with expected 17 public tables."""
    health = check_db_health()
    assert health["status"] == "healthy"
    assert health["database"] == "campus_maintenance"
    assert health["public_tables_count"] == 17
    assert isinstance(health["latency_ms"], float)
    assert health["latency_ms"] >= 0.0


def test_database_connection_release_lifecycle():
    """Verify connections are borrowed and released back to the pool without leaks."""
    manager = DatabaseManager()
    manager.initialize_pool()

    for i in range(5):
        with manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT %s AS step", (i,))
                res = cur.fetchone()
                assert res is not None
                assert res["step"] == i

    manager.close_pool()


def test_transaction_context_manager():
    """Verify transaction context manager executes and commits cleanly."""
    manager = DatabaseManager()
    with manager.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) AS count FROM building")
            row = cur.fetchone()
            assert row is not None
            assert row["count"] == 5
    manager.close_pool()


def test_base_repository_fetch_primitives():
    """Verify BaseRepository fetch_one and fetch_all primitives."""
    # Test fetch_one
    building = BaseRepository.fetch_one(
        "SELECT building_id, building_name FROM building WHERE building_id = %s",
        (1,),
    )
    assert building is not None
    assert building["building_id"] == 1
    assert "Vivekananda" in building["building_name"]

    # Test fetch_all
    categories = BaseRepository.fetch_all("SELECT category_name FROM category ORDER BY category_id")
    assert len(categories) == 6

    # Test non-existent row
    missing = BaseRepository.fetch_one("SELECT * FROM building WHERE building_id = %s", (99999,))
    assert missing is None


def test_graceful_connection_failure_unreachable_host():
    """Verify DatabaseManager gracefully reports failure when connecting to invalid target."""
    unreachable_config = DatabaseConfig(
        host="127.0.0.1",
        port=59999,  # Unused port
        database="nonexistent_db",
        user="invalid_user",
        password="",
        pool_min_size=1,
        pool_max_size=2,
        pool_timeout=1.0,
        connect_timeout=1,
    )
    failing_manager = DatabaseManager(unreachable_config)
    health = failing_manager.check_health()

    assert health["status"] == "unhealthy"
    assert "error" in health
    assert len(health["error"]) > 0
    failing_manager.close_pool()
