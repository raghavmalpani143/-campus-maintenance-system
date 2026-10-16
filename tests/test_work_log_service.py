"""
Unit & Integration Tests for WorkLogService
Covers Positive, Negative, Integration Chain, and Boundary Isolation requirements.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
import pytest

from app.exceptions import (
    AssignmentNotFoundError,
    ImmutableFieldError,
    InvalidDateError,
    InvalidHoursSpentError,
    InvalidWorkDescriptionError,
    WorkLogNotFoundError,
)
from app.repositories.base import BaseRepository
from app.repositories.request import RequestRepository
from app.services.assignment_service import AssignmentService
from app.services.work_log_service import WorkLogService


@pytest.fixture
def service():
    return WorkLogService()


@pytest.fixture
def assignment_service():
    return AssignmentService()


# =============================================================================
# WORK LOG — POSITIVE TESTS
# =============================================================================

def test_pos_1_create_valid_work_log(service, db_conn):
    """Positive 1: Create a valid work log linked to an existing assignment."""
    now = datetime(2026, 10, 1, 14, 30, 0)
    log = service.create_work_log(
        assignment_id=4,  # Assignment 4 for Request 4 (Gurpreet Singh)
        work_description="Cleaned blower assembly and tested air velocity",
        hours_spent=Decimal("3.50"),
        work_date=now,
        conn=db_conn,
    )
    assert log is not None
    assert log["work_log_id"] > 0
    assert log["assignment_id"] == 4
    assert log["hours_spent"] == Decimal("3.50")
    assert log["technician_name"] == "Gurpreet Singh"
    assert log["request_number"] == "REQ-20260925-0004"


def test_pos_2_retrieve_work_log(service, db_conn):
    """Positive 2: Retrieve an existing work log by ID."""
    log = service.get_work_log_by_id(1, conn=db_conn)
    assert log["work_log_id"] == 1
    assert log["assignment_id"] == 1
    assert log["technician_name"] == "Gurpreet Singh"
    assert log["request_number"] == "REQ-20260920-0001"


def test_pos_3_list_work_logs(service, db_conn):
    """Positive 3: List all work logs."""
    logs = service.list_work_logs(conn=db_conn)
    assert len(logs) >= 8


def test_pos_4_filter_by_assignment(service, db_conn):
    """Positive 4: Filter work logs by assignment_id."""
    logs = service.list_work_logs({"assignment_id": 2}, conn=db_conn)
    assert len(logs) == 2
    assert all(wl["assignment_id"] == 2 for wl in logs)
    assert all(wl["technician_name"] == "Dinesh Kumar Verma" for wl in logs)


def test_pos_5_filter_by_request(service, db_conn):
    """Positive 5: Filter work logs by request_id (resolved through assignment)."""
    logs = service.list_work_logs({"request_id": 3}, conn=db_conn)
    assert len(logs) == 1
    assert logs[0]["request_number"] == "REQ-20260922-0003"
    assert logs[0]["technician_name"] == "Mahesh Chandra"


def test_pos_6_filter_by_technician(service, db_conn):
    """Positive 6: Filter work logs by technician_id (resolved through assignment)."""
    logs = service.list_work_logs({"technician_id": 3}, conn=db_conn)
    assert len(logs) >= 2
    assert all(wl["technician_name"] == "Gurpreet Singh" for wl in logs)


def test_pos_7_filter_by_date(service, db_conn):
    """Positive 7: Filter work logs by date range."""
    d_from = datetime(2026, 9, 21, 0, 0, 0)
    d_to = datetime(2026, 9, 23, 23, 59, 59)
    logs = service.list_work_logs({"date_from": d_from, "date_to": d_to}, conn=db_conn)
    assert len(logs) >= 2
    assert all(d_from <= wl["work_date"] <= d_to for wl in logs)


# =============================================================================
# WORK LOG — NEGATIVE TESTS
# =============================================================================

def test_neg_1_nonexistent_assignment(service, db_conn):
    """Negative 1: Creating work log for nonexistent assignment raises AssignmentNotFoundError."""
    with pytest.raises(AssignmentNotFoundError, match="Assignment with ID 99999 does not exist"):
        service.create_work_log(
            assignment_id=99999,
            work_description="Valid description",
            hours_spent=2.0,
            conn=db_conn,
        )


def test_neg_2_missing_work_description(service, db_conn):
    """Negative 2: Missing or blank work description raises InvalidWorkDescriptionError."""
    with pytest.raises(InvalidWorkDescriptionError):
        service.create_work_log(
            assignment_id=1,
            work_description="",
            hours_spent=2.0,
            conn=db_conn,
        )

    with pytest.raises(InvalidWorkDescriptionError):
        service.create_work_log(
            assignment_id=1,
            work_description="   \n\t  ",
            hours_spent=2.0,
            conn=db_conn,
        )


def test_neg_3_invalid_hours(service, db_conn):
    """Negative 3: Negative or non-numeric hours raises InvalidHoursSpentError."""
    with pytest.raises(InvalidHoursSpentError, match="cannot be negative"):
        service.create_work_log(
            assignment_id=1,
            work_description="Repairing leak",
            hours_spent=-1.5,
            conn=db_conn,
        )

    with pytest.raises(InvalidHoursSpentError, match="must be a numeric value"):
        service.create_work_log(
            assignment_id=1,
            work_description="Repairing leak",
            hours_spent="two hours",  # type: ignore
            conn=db_conn,
        )


def test_neg_4_invalid_date(service, db_conn):
    """Negative 4: Future work date raises InvalidDateError."""
    future = datetime.now() + timedelta(days=5)
    with pytest.raises(InvalidDateError, match="cannot be in the future"):
        service.create_work_log(
            assignment_id=1,
            work_description="Completed future checkup",
            hours_spent=1.0,
            work_date=future,
            conn=db_conn,
        )


def test_neg_5_missing_required_fields(service, db_conn):
    """Negative 5: Missing required fields raises TypeError."""
    with pytest.raises(TypeError):
        service.create_work_log(conn=db_conn)  # type: ignore


def test_neg_6_invalid_update_fields(service, db_conn):
    """Negative 6: Updating disallowed fields on work log raises ImmutableFieldError."""
    with pytest.raises(ImmutableFieldError, match="work_log_id"):
        service.update_work_log(
            work_log_id=1,
            updates={"work_log_id": 999},
            conn=db_conn,
        )

    with pytest.raises(ImmutableFieldError, match="assignment_id"):
        service.update_work_log(
            work_log_id=1,
            updates={"assignment_id": 999},
            conn=db_conn,
        )


# =============================================================================
# INTEGRATION CHAIN & STRICT BOUNDARY VERIFICATION
# =============================================================================

def test_full_chain_request_to_assignment_to_work_log(service, assignment_service, db_conn):
    """
    Integration: Prove foreign-key chain works end-to-end:
    Existing Request -> Assignment -> Work Log.
    """
    now = datetime(2026, 10, 1, 9, 0, 0)
    # Step 1: Create assignment for Request 8 (Loose floor tiles)
    assignment = assignment_service.create_assignment(
        request_id=8,
        technician_id=4,  # Arunachalam P. (Civil & Carpentry)
        assigned_date=now,
        status="In Progress",
        conn=db_conn,
    )
    assign_id = assignment["assignment_id"]
    assert assign_id > 0

    # Step 2: Create work log for the new assignment
    work_log = service.create_work_log(
        assignment_id=assign_id,
        work_description="Chiseled loose mortar and leveled tile substrate",
        hours_spent=Decimal("2.25"),
        work_date=now + timedelta(hours=2),
        conn=db_conn,
    )
    assert work_log["work_log_id"] > 0
    assert work_log["assignment_id"] == assign_id
    assert work_log["request_id"] == 8
    assert work_log["request_number"] == "REQ-20260929-0008"
    assert work_log["technician_name"] == "Arunachalam P."
    assert work_log["hours_spent"] == Decimal("2.25")


def test_creating_assignment_and_work_log_does_not_modify_other_tables(
    service, assignment_service, db_conn
):
    """
    Strict Scope Boundary Verification:
    Creating an assignment or work log must NOT unexpectedly modify:
    - REQUEST.StatusID
    - STATUS_HISTORY
    - MATERIAL
    - WORK_LOG_MATERIAL
    - COST
    """
    req_repo = RequestRepository()

    # Capture initial table states
    req_before = req_repo.get_by_id(8, conn=db_conn)
    assert req_before is not None
    status_before = req_before["status_id"]

    history_count_before = len(req_repo.get_status_history_for_request(8, conn=db_conn))
    material_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM material", conn=db_conn)["c"]
    wlm_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM work_log_material", conn=db_conn)["c"]
    cost_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM cost", conn=db_conn)["c"]

    # 1. Create Assignment
    assignment = assignment_service.create_assignment(
        request_id=8,
        technician_id=4,
        conn=db_conn,
    )

    # 2. Create Work Log
    work_log = service.create_work_log(
        assignment_id=assignment["assignment_id"],
        work_description="Boundary test work log",
        hours_spent=Decimal("1.50"),
        conn=db_conn,
    )

    # Assert REQUEST.status_id is unchanged
    req_after = req_repo.get_by_id(8, conn=db_conn)
    assert req_after["status_id"] == status_before

    # Assert STATUS_HISTORY is unchanged
    history_count_after = len(req_repo.get_status_history_for_request(8, conn=db_conn))
    assert history_count_after == history_count_before

    # Assert MATERIAL, WORK_LOG_MATERIAL, COST row counts are completely unchanged
    material_count_after = BaseRepository.fetch_one("SELECT count(*) AS c FROM material", conn=db_conn)["c"]
    wlm_count_after = BaseRepository.fetch_one("SELECT count(*) AS c FROM work_log_material", conn=db_conn)["c"]
    cost_count_after = BaseRepository.fetch_one("SELECT count(*) AS c FROM cost", conn=db_conn)["c"]

    assert material_count_after == material_count_before
    assert wlm_count_after == wlm_count_before
    assert cost_count_after == cost_count_before
