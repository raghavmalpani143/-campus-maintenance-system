"""
Pytest Configuration and Test Fixtures
"""

from __future__ import annotations

import os
import pytest
from app.config import get_config
from app.db import DatabaseManager, get_db_manager


@pytest.fixture(scope="session")
def app_config():
    """Provide application configuration fixture."""
    return get_config(reload=True)


@pytest.fixture(scope="session", autouse=True)
def cleanup_global_db_pool():
    """Ensure global connection pool is cleanly closed at test session end."""
    yield
    from app.db import _db_manager_instance
    if _db_manager_instance is not None:
        _db_manager_instance.close_pool()


@pytest.fixture(scope="function")
def db_manager():
    """Provide a managed DatabaseManager fixture that closes after test execution."""
    manager = get_db_manager()
    yield manager
    manager.close_pool()


@pytest.fixture(scope="function")
def db_conn():
    """
    Provide an isolated database connection wrapped in an outer transaction
    that is unconditionally rolled back upon test completion.
    Guarantees no persistent modifications to the database.
    """
    from app.db import get_connection
    with get_connection() as conn:
        trans = conn.transaction()
        trans.__enter__()
        try:
            yield conn
        finally:
            trans.__exit__(RuntimeError, RuntimeError("Rollback test transaction"), None)


@pytest.fixture(autouse=True)
def clean_test_requests():
    """Ensure no test-generated records linger in the database."""
    yield
    from app.db import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cost WHERE cost_id > 14;")
            cur.execute("DELETE FROM work_log_material WHERE work_log_id > 8 OR material_id > 10;")
            cur.execute("DELETE FROM work_log WHERE work_log_id > 8;")
            cur.execute("DELETE FROM assignment WHERE assignment_id > 9;")
            cur.execute("DELETE FROM request WHERE request_number LIKE 'TEST-%' OR request_number LIKE 'REQ-9999%' OR request_id > 10;")
            cur.execute("DELETE FROM material WHERE material_id > 10;")
            cur.execute("UPDATE request SET status_id = 1, closed_date = NULL, resolution_description = NULL, closed_by = NULL WHERE request_id = 9 AND status_id != 1;")
        conn.commit()


@pytest.fixture
def isolated_work_log(db_conn):
    """
    Provide an isolated work log on Assignment 1 (Request 1)
    within the isolated db_conn transaction so tests can insert/verify
    materials without colliding with existing seed records.
    """
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO work_log (assignment_id, work_date, work_description, hours_spent)
            VALUES (1, '2026-10-01 10:00:00', 'Isolated test work log for material operations', 1.00)
            RETURNING work_log_id;
            """
        )
        return cur.fetchone()["work_log_id"]
