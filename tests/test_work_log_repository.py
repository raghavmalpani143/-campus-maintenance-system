"""
Unit & Integration Tests for WorkLogRepository
Verifies parameterized SQL execution, relational joins through ASSIGNMENT to REQUEST and TECHNICIAN.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import pytest

from app.repositories.work_log import WorkLogRepository


@pytest.fixture
def repo():
    return WorkLogRepository()


def test_repo_create_and_get_work_log(repo, db_conn):
    """Test creating a work log and retrieving it with joined assignment, request, and technician metadata."""
    now = datetime(2026, 10, 1, 14, 0, 0)
    created = repo.create_work_log(
        {
            "assignment_id": 4,  # Assignment 4 for Request 4 (Gurpreet Singh)
            "work_date": now,
            "work_description": "Inspected fume hood exhaust motor and aligned pulleys",
            "hours_spent": Decimal("2.50"),
        },
        conn=db_conn,
    )
    assert created["work_log_id"] is not None
    assert created["assignment_id"] == 4
    assert created["hours_spent"] == Decimal("2.50")

    retrieved = repo.get_by_id(created["work_log_id"], conn=db_conn)
    assert retrieved is not None
    assert retrieved["work_log_id"] == created["work_log_id"]
    assert retrieved["assignment_id"] == 4
    assert retrieved["request_id"] == 4
    assert retrieved["request_number"] == "REQ-20260925-0004"
    assert retrieved["technician_name"] == "Gurpreet Singh"
    assert retrieved["technician_department"] == "HVAC & Refrigeration"
    assert retrieved["hours_spent"] == Decimal("2.50")


def test_repo_list_work_logs_and_filters(repo, db_conn):
    """Test listing and filtering work logs across assignments, requests, technicians, and dates."""
    # List all
    all_logs = repo.list_work_logs(conn=db_conn)
    assert len(all_logs) >= 8

    # Filter by assignment_id = 1 (Request 1 has 2 seeded work logs)
    assign1_logs = repo.list_work_logs({"assignment_id": 1}, conn=db_conn)
    assert len(assign1_logs) == 2
    assert all(wl["technician_name"] == "Gurpreet Singh" for wl in assign1_logs)

    # Filter by request_id = 1 (joined through assignment; Request 1 has 2 work logs)
    req1_logs = repo.list_work_logs({"request_id": 1}, conn=db_conn)
    assert len(req1_logs) == 2
    assert req1_logs[0]["request_number"] == "REQ-20260920-0001"

    # Filter by technician_id = 1 (Mahesh Chandra has 2 seeded work logs)
    tech1_logs = repo.list_work_logs({"technician_id": 1}, conn=db_conn)
    assert len(tech1_logs) == 2
    assert all(wl["technician_name"] == "Mahesh Chandra" for wl in tech1_logs)

    # Search filter
    search_logs = repo.list_work_logs({"search": "refrigerant"}, conn=db_conn)
    assert len(search_logs) >= 1
    assert any("refrigerant" in wl["work_description"].lower() for wl in search_logs)


def test_repo_update_work_log(repo, db_conn):
    """Test updating permitted mutable fields on a work log."""
    now = datetime(2026, 10, 1, 15, 0, 0)
    created = repo.create_work_log(
        {
            "assignment_id": 5,
            "work_date": now,
            "work_description": "Initial diagnostic check",
            "hours_spent": Decimal("1.00"),
        },
        conn=db_conn,
    )
    wl_id = created["work_log_id"]

    updated = repo.update_work_log(
        wl_id,
        {
            "work_description": "Completed diagnostic check and replaced fuse",
            "hours_spent": Decimal("2.00"),
        },
        conn=db_conn,
    )
    assert updated is not None
    assert updated["work_description"] == "Completed diagnostic check and replaced fuse"
    assert updated["hours_spent"] == Decimal("2.00")


def test_repo_assignment_exists(repo, db_conn):
    """Test checking existence of assignments."""
    assert repo.assignment_exists(1, conn=db_conn) is True
    assert repo.assignment_exists(99999, conn=db_conn) is False
