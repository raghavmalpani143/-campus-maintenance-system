"""
Unit Tests for Configuration Loading & Validation
"""

from __future__ import annotations

import os
import pytest
from app.config import AppConfig, DatabaseConfig, get_config


def test_default_config_loading():
    """Verify default configuration loads properly from environment/.env."""
    config = get_config(reload=True)
    assert config.db.database == "campus_maintenance"
    assert config.db.host in ("localhost", "127.0.0.1")
    assert config.db.port == 5432
    assert config.db.pool_min_size >= 1
    assert config.db.pool_max_size >= config.db.pool_min_size


def test_conninfo_and_dict():
    """Verify connection info string and dictionary generation."""
    db_config = DatabaseConfig(
        host="localhost",
        port=5432,
        database="campus_maintenance",
        user="postgres",
        password="secretpassword",
        pool_min_size=2,
        pool_max_size=5,
        pool_timeout=15.0,
        connect_timeout=5,
    )
    conninfo = db_config.get_conninfo()
    assert "host=localhost" in conninfo
    assert "port=5432" in conninfo
    assert "dbname=campus_maintenance" in conninfo
    assert "user=postgres" in conninfo
    assert "password=secretpassword" in conninfo
    assert "connect_timeout=5" in conninfo

    kwargs = db_config.to_dict()
    assert kwargs["host"] == "localhost"
    assert kwargs["port"] == 5432
    assert kwargs["dbname"] == "campus_maintenance"
    assert kwargs["user"] == "postgres"
    assert kwargs["password"] == "secretpassword"
    assert kwargs["connect_timeout"] == 5


def test_invalid_port_raises_error(monkeypatch):
    """Verify non-integer DB_PORT raises ValueError."""
    monkeypatch.setenv("DB_PORT", "not_a_number")
    with pytest.raises(ValueError, match="Invalid DB_PORT"):
        DatabaseConfig.from_env()


def test_invalid_pool_bounds_raises_error(monkeypatch):
    """Verify pool_max_size < pool_min_size raises ValueError."""
    monkeypatch.setenv("DB_POOL_MIN_SIZE", "5")
    monkeypatch.setenv("DB_POOL_MAX_SIZE", "2")
    with pytest.raises(ValueError, match="DB_POOL_MAX_SIZE must be greater"):
        DatabaseConfig.from_env()


def test_invalid_pool_min_size_raises_error(monkeypatch):
    """Verify pool_min_size < 1 raises ValueError."""
    monkeypatch.setenv("DB_POOL_MIN_SIZE", "0")
    with pytest.raises(ValueError, match="DB_POOL_MIN_SIZE must be at least 1"):
        DatabaseConfig.from_env()
