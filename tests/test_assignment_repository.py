"""
Unit & Integration Tests for AssignmentRepository
Verifies parameterized SQL execution, relational joins with REQUEST and TECHNICIAN.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import pytest

from app.repositories.assignment import AssignmentRepository


@pytest.fixture
def repo():
    return AssignmentRepository()


def test_repo_create_and_get_assignment(repo, db_conn):
    """Test creating an assignment and retrieving it with joined request and technician data."""
    now = datetime(2026, 10, 1, 9, 0, 0)
    due = now + timedelta(days=2)
    created = repo.create_assignment(
        {
            "request_id": 8,  # Open request REQ-20260929-0008
            "technician_id": 4, # Arunachalam P. (Civil & Carpentry)
            "assigned_date": now,
            "due_date": due,
            "status": "Assigned",
        },
        conn=db_conn,
    )
    assert created["assignment_id"] is not None
    assert created["request_id"] == 8
    assert created["technician_id"] == 4

    retrieved = repo.get_by_id(created["assignment_id"], conn=db_conn)
    assert retrieved is not None
    assert retrieved["assignment_id"] == created["assignment_id"]
    assert retrieved["request_number"] == "REQ-20260929-0008"
    assert retrieved["technician_name"] == "Arunachalam P."
    assert retrieved["technician_department"] == "Civil & Carpentry"
    assert retrieved["assignment_status"] == "Assigned"


def test_repo_list_assignments_and_filters(repo, db_conn):
    """Test listing and filtering assignments by request, technician, status, and dates."""
    # List all
    all_assignments = repo.list_assignments(conn=db_conn)
    assert len(all_assignments) >= 9

    # Filter by technician_id = 3 (Gurpreet Singh)
    tech3_assignments = repo.list_assignments({"technician_id": 3}, conn=db_conn)
    assert len(tech3_assignments) >= 3
    assert all(a["technician_name"] == "Gurpreet Singh" for a in tech3_assignments)

    # Filter by request_id = 1
    req1_assignments = repo.list_assignments({"request_id": 1}, conn=db_conn)
    assert len(req1_assignments) == 1
    assert req1_assignments[0]["request_number"] == "REQ-20260920-0001"

    # Filter by status = 'Completed'
    completed = repo.list_assignments({"status": "Completed"}, conn=db_conn)
    assert len(completed) >= 4
    assert all(a["assignment_status"] == "Completed" for a in completed)


def test_repo_update_assignment(repo, db_conn):
    """Test updating permitted mutable fields on an assignment record."""
    now = datetime(2026, 10, 1, 9, 0, 0)
    created = repo.create_assignment(
        {
            "request_id": 9,
            "technician_id": 2,
            "assigned_date": now,
            "due_date": now + timedelta(days=1),
            "status": "Assigned",
        },
        conn=db_conn,
    )
    assign_id = created["assignment_id"]

    new_due = now + timedelta(days=3)
    updated = repo.update_assignment(
        assign_id,
        {
            "status": "In Progress",
            "due_date": new_due,
        },
        conn=db_conn,
    )
    assert updated is not None
    assert updated["assignment_status"] == "In Progress"
    assert updated["due_date"] == new_due


def test_repo_checkers(repo, db_conn):
    """Test repository existence check primitives."""
    assert repo.request_exists(1, conn=db_conn) is True
    assert repo.request_exists(99999, conn=db_conn) is False

    assert repo.technician_exists(1, conn=db_conn) is True
    assert repo.technician_exists(99999, conn=db_conn) is False

    tech = repo.get_technician(1, conn=db_conn)
    assert tech is not None
    assert tech["full_name"] == "Mahesh Chandra"
