"""
Unit & Integration Tests for AssignmentService
Covers all Positive, Negative, Update, and Side-Effect Boundary requirements.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import pytest

from app.exceptions import (
    AssignmentNotFoundError,
    ImmutableFieldError,
    InvalidAssignmentStatusError,
    InvalidDateError,
    RequestNotFoundError,
    TechnicianNotFoundError,
)
from app.repositories.request import RequestRepository
from app.services.assignment_service import AssignmentService


@pytest.fixture
def service():
    return AssignmentService()


# =============================================================================
# ASSIGNMENT — POSITIVE TESTS
# =============================================================================

def test_pos_1_create_valid_assignment(service, db_conn):
    """Positive 1: Create a valid technician assignment."""
    now = datetime(2026, 10, 1, 9, 30, 0)
    due = now + timedelta(days=2)
    assignment = service.create_assignment(
        request_id=8,       # REQ-20260929-0008 (Loose floor tiles)
        technician_id=4,    # Arunachalam P. (Civil & Carpentry)
        assigned_date=now,
        due_date=due,
        status="Assigned",
        conn=db_conn,
    )
    assert assignment is not None
    assert assignment["assignment_id"] > 0
    assert assignment["request_id"] == 8
    assert assignment["technician_id"] == 4
    assert assignment["request_number"] == "REQ-20260929-0008"
    assert assignment["technician_name"] == "Arunachalam P."
    assert assignment["assignment_status"] == "Assigned"


def test_pos_2_retrieve_assignment(service, db_conn):
    """Positive 2: Retrieve an existing assignment by primary key."""
    assignment = service.get_assignment_by_id(1, conn=db_conn)
    assert assignment["assignment_id"] == 1
    assert assignment["request_id"] == 1
    assert assignment["technician_name"] == "Gurpreet Singh"
    assert assignment["assignment_status"] == "Completed"


def test_pos_3_list_assignments(service, db_conn):
    """Positive 3: List all assignments."""
    assignments = service.list_assignments(conn=db_conn)
    assert len(assignments) >= 9


def test_pos_4_filter_by_request(service, db_conn):
    """Positive 4: Filter assignments by request_id."""
    # Request 6 has two assignments in seed data (original and reassigned)
    assignments = service.list_assignments({"request_id": 6}, conn=db_conn)
    assert len(assignments) == 2
    assert all(a["request_id"] == 6 for a in assignments)


def test_pos_5_filter_by_technician(service, db_conn):
    """Positive 5: Filter assignments by technician_id."""
    # Tech 1 (Mahesh Chandra) has multiple assignments
    assignments = service.list_assignments({"technician_id": 1}, conn=db_conn)
    assert len(assignments) >= 3
    assert all(a["technician_id"] == 1 for a in assignments)
    assert all(a["technician_name"] == "Mahesh Chandra" for a in assignments)


def test_pos_6_filter_by_status(service, db_conn):
    """Positive 6: Filter assignments by assignment status."""
    in_prog = service.list_assignments({"status": "In Progress"}, conn=db_conn)
    assert len(in_prog) >= 3
    assert all(a["assignment_status"] == "In Progress" for a in in_prog)


def test_pos_7_update_permitted_assignment_fields(service, db_conn):
    """Positive 7: Update permitted mutable fields (status, due_date)."""
    now = datetime(2026, 10, 1, 10, 0, 0)
    created = service.create_assignment(
        request_id=9,
        technician_id=2,  # Dinesh Kumar Verma
        assigned_date=now,
        due_date=now + timedelta(days=1),
        status="Assigned",
        conn=db_conn,
    )
    assign_id = created["assignment_id"]

    new_due = now + timedelta(days=3)
    updated = service.update_assignment(
        assignment_id=assign_id,
        updates={
            "status": "In Progress",
            "due_date": new_due,
        },
        conn=db_conn,
    )
    assert updated["assignment_status"] == "In Progress"
    assert updated["due_date"] == new_due


# =============================================================================
# ASSIGNMENT — NEGATIVE TESTS
# =============================================================================

def test_neg_1_nonexistent_request(service, db_conn):
    """Negative 1: Creating assignment for nonexistent request raises RequestNotFoundError."""
    with pytest.raises(RequestNotFoundError, match="request with ID 99999 does not exist"):
        service.create_assignment(
            request_id=99999,
            technician_id=1,
            conn=db_conn,
        )


def test_neg_2_nonexistent_technician(service, db_conn):
    """Negative 2: Creating assignment for nonexistent technician raises TechnicianNotFoundError."""
    with pytest.raises(TechnicianNotFoundError, match="Technician with ID 99999 does not exist"):
        service.create_assignment(
            request_id=1,
            technician_id=99999,
            conn=db_conn,
        )


def test_neg_3_invalid_assignment_status(service, db_conn):
    """Negative 3: Invalid assignment status raises InvalidAssignmentStatusError."""
    with pytest.raises(InvalidAssignmentStatusError, match="Invalid assignment status 'InvalidStatus'"):
        service.create_assignment(
            request_id=8,
            technician_id=1,
            status="InvalidStatus",
            conn=db_conn,
        )


def test_neg_4_missing_required_fields(service, db_conn):
    """Negative 4: Missing required fields raises appropriate error."""
    with pytest.raises(TypeError):
        service.create_assignment(conn=db_conn)  # type: ignore


def test_neg_5_invalid_date_type(service, db_conn):
    """Negative 5: Passing non-datetime for assigned_date raises InvalidDateError."""
    with pytest.raises(InvalidDateError, match="Assigned date must be a valid datetime"):
        service.create_assignment(
            request_id=8,
            technician_id=1,
            assigned_date="not-a-datetime",  # type: ignore
            conn=db_conn,
        )


def test_neg_6_due_date_earlier_than_assigned_date(service, db_conn):
    """Negative 6: DueDate earlier than AssignedDate raises InvalidDateError."""
    now = datetime(2026, 10, 1, 10, 0, 0)
    past_due = now - timedelta(hours=2)
    with pytest.raises(InvalidDateError, match="Due date .* cannot precede assigned date"):
        service.create_assignment(
            request_id=8,
            technician_id=1,
            assigned_date=now,
            due_date=past_due,
            conn=db_conn,
        )


def test_neg_7_invalid_update_field(service, db_conn):
    """Negative 7: Attempting to update a non-whitelisted field raises ImmutableFieldError."""
    with pytest.raises(ImmutableFieldError, match="not permitted to be updated directly"):
        service.update_assignment(
            assignment_id=1,
            updates={"non_existent_field": "bad_value"},
            conn=db_conn,
        )


def test_neg_8_attempt_to_mutate_immutable_identifiers(service, db_conn):
    """Negative 8: Attempting to update assignment_id, request_id, or technician_id raises ImmutableFieldError."""
    with pytest.raises(ImmutableFieldError, match="request_id"):
        service.update_assignment(
            assignment_id=1,
            updates={"request_id": 999},
            conn=db_conn,
        )

    with pytest.raises(ImmutableFieldError, match="assignment_id"):
        service.update_assignment(
            assignment_id=1,
            updates={"assignment_id": 999},
            conn=db_conn,
        )

    # Prove technician_id cannot be mutated directly on an existing assignment
    with pytest.raises(ImmutableFieldError, match="technician_id"):
        service.update_assignment(
            assignment_id=1,
            updates={"technician_id": 2},
            conn=db_conn,
        )


def test_assignment_reassignment_preserves_documented_pattern(service, db_conn):
    """
    Verify documented reassignment pattern:
    1. Mark existing assignment status as 'Reassigned'
    2. Changing technician is NOT performed by mutating technician_id on the existing row
    3. Proper reassignment creates a NEW assignment row for the new technician
    """
    # 1. Update existing assignment status to 'Reassigned'
    updated = service.update_assignment(
        assignment_id=1,
        updates={"status": "Reassigned"},
        conn=db_conn,
    )
    assert updated["assignment_status"] == "Reassigned"

    # 2. Attempting to directly mutate technician_id on assignment 1 is rejected
    with pytest.raises(ImmutableFieldError, match="technician_id"):
        service.update_assignment(
            assignment_id=1,
            updates={"technician_id": 2},
            conn=db_conn,
        )

    # 3. Documented reassignment creates a new assignment row for the new technician
    new_assignment = service.create_assignment(
        request_id=1,
        technician_id=2,  # Dinesh Kumar Verma
        status="Assigned",
        conn=db_conn,
    )
    assert new_assignment["assignment_id"] != 1
    assert new_assignment["technician_id"] == 2
    assert new_assignment["assignment_status"] == "Assigned"


# =============================================================================
# STATUS BOUNDARY ISOLATION
# =============================================================================

def test_assignment_creation_does_not_modify_request_status_or_history(service, db_conn):
    """
    Verify creating or updating an ASSIGNMENT does NOT modify
    REQUEST.status_id or insert a STATUS_HISTORY row.
    """
    req_repo = RequestRepository()
    req_before = req_repo.get_by_id(8, conn=db_conn)
    assert req_before is not None
    status_before = req_before["status_id"]
    history_before = req_repo.get_status_history_for_request(8, conn=db_conn)

    # Create assignment
    assignment = service.create_assignment(
        request_id=8,
        technician_id=4,
        conn=db_conn,
    )
    assert assignment["assignment_id"] is not None

    # Update assignment
    service.update_assignment(
        assignment_id=assignment["assignment_id"],
        updates={"status": "In Progress"},
        conn=db_conn,
    )

    # Check request state remains identical
    req_after = req_repo.get_by_id(8, conn=db_conn)
    assert req_after is not None
    assert req_after["status_id"] == status_before

    history_after = req_repo.get_status_history_for_request(8, conn=db_conn)
    assert len(history_after) == len(history_before)
