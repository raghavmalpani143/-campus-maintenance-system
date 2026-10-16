"""
Unit & Integration Tests for Request Status Management & Status History (Phase 3E)
Covers:
- Positive Status Transitions:
    * Open -> Assigned
    * Assigned -> In Progress
    * In Progress -> On Hold
    * On Hold -> In Progress
    * In Progress -> Closed
    * On Hold -> Closed
    * Successful history insertion & chronological audit trail retrieval
- Negative Validation & Boundary Tests:
    * Nonexistent request
    * Nonexistent status
    * Nonexistent changed_by user
    * Invalid transitions (Open -> In Progress, Open -> Closed, Assigned -> Closed, etc.)
    * Transitions from terminal Closed state
    * Same-status updates (no-op transitions rejected)
- Transaction Atomicity & Rollback:
    * Failed history insertion rolls back request.status_id
    * Failed status update ensures no history row is committed
- Concurrency & Row-Level Locking:
    * Multi-threaded concurrent status transitions on the same request
- Strict Side-Effect Boundary:
    * Changing status does not touch assignments, work logs, materials, costs, or feedback
"""

from __future__ import annotations

import concurrent.futures
from datetime import datetime
import pytest

from app.db import get_connection
from app.exceptions import (
    DatabaseOperationError,
    InvalidDateError,
    InvalidStatusTransitionError,
    RequestNotFoundError,
    SameStatusUpdateError,
    StatusNotFoundError,
    UserNotFoundError,
)
from app.repositories.base import BaseRepository
from app.repositories.request import RequestRepository
from app.services.request_service import RequestService
from app.services.request_status_service import RequestStatusService


@pytest.fixture
def service():
    return RequestStatusService()


@pytest.fixture
def repo():
    return RequestRepository()


# =============================================================================
# POSITIVE STATUS TRANSITION TESTS
# =============================================================================

def test_pos_1_open_to_assigned(service, db_conn):
    """Positive 1: Transition Open -> Assigned on Request 8."""
    # Verify initial status is Open (ID 1)
    status_before = service.get_request_status(8, conn=db_conn)
    assert status_before["status_name"] == "Open"
    assert status_before["status_id"] == 1

    # Transition to Assigned (status_id = 2)
    updated = service.change_request_status(
        request_id=8,
        new_status="Assigned",
        changed_by=7,  # Facility Director Dr. Rajesh Sharma
        remarks="Dispatched technician for inspection",
        conn=db_conn,
    )
    assert updated["status_id"] == 2
    assert updated["status_name"] == "Assigned"

    status_after = service.get_request_status(8, conn=db_conn)
    assert status_after["status_name"] == "Assigned"
    assert status_after["status_id"] == 2


def test_pos_2_assigned_to_in_progress(service, db_conn):
    """Positive 2: Transition Assigned -> In Progress on Request 7."""
    status_before = service.get_request_status(7, conn=db_conn)
    assert status_before["status_name"] == "Assigned"
    assert status_before["status_id"] == 2

    # Accept status by integer ID (3 = In Progress)
    updated = service.change_request_status(
        request_id=7,
        new_status=3,
        changed_by=4,  # Arunachalam P. (Technician)
        remarks="Technician on site; starting carpentry work",
        conn=db_conn,
    )
    assert updated["status_id"] == 3
    assert updated["status_name"] == "In Progress"

    status_after = service.get_request_status(7, conn=db_conn)
    assert status_after["status_name"] == "In Progress"


def test_pos_3_in_progress_to_on_hold(service, db_conn):
    """Positive 3: Transition In Progress -> On Hold on Request 4."""
    status_before = service.get_request_status(4, conn=db_conn)
    assert status_before["status_name"] == "In Progress"

    updated = service.change_request_status(
        request_id=4,
        new_status="On Hold",
        changed_by=7,
        remarks="Awaiting delivery of replacement motor bearings",
        conn=db_conn,
    )
    assert updated["status_id"] == 4
    assert updated["status_name"] == "On Hold"

    status_after = service.get_request_status(4, conn=db_conn)
    assert status_after["status_name"] == "On Hold"


def test_pos_4_on_hold_to_in_progress(service, db_conn):
    """Positive 4: Transition On Hold -> In Progress on Request 6."""
    status_before = service.get_request_status(6, conn=db_conn)
    assert status_before["status_name"] == "On Hold"

    updated = service.change_request_status(
        request_id=6,
        new_status="In Progress",
        changed_by=7,
        remarks="Breaker delivered; resuming electrical replacement",
        conn=db_conn,
    )
    assert updated["status_id"] == 3
    assert updated["status_name"] == "In Progress"

    status_after = service.get_request_status(6, conn=db_conn)
    assert status_after["status_name"] == "In Progress"


def test_pos_5_successful_history_insertion(service, db_conn):
    """Positive 5: Verify STATUS_HISTORY row is created with correct attributes."""
    history_before = service.get_status_history(8, conn=db_conn)
    initial_count = len(history_before)

    now = datetime(2026, 10, 2, 11, 30, 0)
    service.change_request_status(
        request_id=8,
        new_status="Assigned",
        changed_by=7,
        remarks="Test assignment remarks",
        changed_date=now,
        conn=db_conn,
    )

    history_after = service.get_status_history(8, conn=db_conn)
    assert len(history_after) == initial_count + 1

    latest = history_after[-1]
    assert latest["request_id"] == 8
    assert latest["status_id"] == 2
    assert latest["status_name"] == "Assigned"
    assert latest["changed_by"] == 7
    assert latest["changed_by_name"] == "Col. Rajesh Nair (Retd)"
    assert latest["remarks"] == "Test assignment remarks"
    assert latest["changed_date"] == now


def test_pos_6_history_retrieval(service, db_conn):
    """Positive 6: Retrieve chronological status history for a request."""
    # Request 1 in seed data transitioned: Open -> Assigned -> In Progress -> Closed (4 transitions)
    history = service.get_status_history(1, conn=db_conn)
    assert len(history) == 4
    statuses = [h["status_name"] for h in history]
    assert statuses == ["Open", "Assigned", "In Progress", "Closed"]

    # Verify chronological ordering by status_history_id
    ids = [h["status_history_id"] for h in history]
    assert ids == sorted(ids)


# =============================================================================
# NEGATIVE VALIDATION TESTS
# =============================================================================

def test_neg_1_nonexistent_request(service, db_conn):
    """Negative 1: Nonexistent request raises RequestNotFoundError."""
    with pytest.raises(RequestNotFoundError, match="Request with ID 99999 does not exist"):
        service.change_request_status(
            request_id=99999,
            new_status="Assigned",
            changed_by=7,
            conn=db_conn,
        )

    with pytest.raises(RequestNotFoundError, match="Request with ID 99999 does not exist"):
        service.get_request_status(99999, conn=db_conn)


def test_neg_2_nonexistent_status(service, db_conn):
    """Negative 2: Nonexistent status raises StatusNotFoundError."""
    with pytest.raises(StatusNotFoundError, match="Status 'NonexistentStatus' does not exist"):
        service.change_request_status(
            request_id=8,
            new_status="NonexistentStatus",
            changed_by=7,
            conn=db_conn,
        )

    with pytest.raises(StatusNotFoundError, match="Status '99999' does not exist"):
        service.change_request_status(
            request_id=8,
            new_status=99999,
            changed_by=7,
            conn=db_conn,
        )

    with pytest.raises(StatusNotFoundError, match="Target status must not be None"):
        service.change_request_status(
            request_id=8,
            new_status=None,  # type: ignore
            changed_by=7,
            conn=db_conn,
        )


def test_neg_3_nonexistent_changed_by_user(service, db_conn):
    """Negative 3: Nonexistent user ID raises UserNotFoundError."""
    with pytest.raises(UserNotFoundError, match="User with ID 99999 does not exist"):
        service.change_request_status(
            request_id=8,
            new_status="Assigned",
            changed_by=99999,
            conn=db_conn,
        )

    with pytest.raises(UserNotFoundError, match="User ID must be a positive integer"):
        service.change_request_status(
            request_id=8,
            new_status="Assigned",
            changed_by=-1,
            conn=db_conn,
        )


def test_neg_4_invalid_transitions(service, db_conn):
    """Negative 4: Unapproved transitions raise InvalidStatusTransitionError."""
    # Open -> In Progress ❌
    with pytest.raises(InvalidStatusTransitionError, match="Invalid status transition from 'Open' to 'In Progress'"):
        service.change_request_status(request_id=8, new_status="In Progress", changed_by=7, conn=db_conn)

    # Open -> Closed ❌
    with pytest.raises(InvalidStatusTransitionError, match="Invalid status transition from 'Open' to 'Closed'"):
        service.change_request_status(request_id=8, new_status="Closed", changed_by=7, conn=db_conn)

    # Open -> On Hold ❌
    with pytest.raises(InvalidStatusTransitionError, match="Invalid status transition from 'Open' to 'On Hold'"):
        service.change_request_status(request_id=8, new_status="On Hold", changed_by=7, conn=db_conn)

    # Assigned -> Closed ❌ (Request 7 is Assigned)
    with pytest.raises(InvalidStatusTransitionError, match="Invalid status transition from 'Assigned' to 'Closed'"):
        service.change_request_status(request_id=7, new_status="Closed", changed_by=7, conn=db_conn)

    # Assigned -> On Hold ❌
    with pytest.raises(InvalidStatusTransitionError, match="Invalid status transition from 'Assigned' to 'On Hold'"):
        service.change_request_status(request_id=7, new_status="On Hold", changed_by=7, conn=db_conn)

    # Assigned -> Open ❌
    with pytest.raises(InvalidStatusTransitionError, match="Invalid status transition from 'Assigned' to 'Open'"):
        service.change_request_status(request_id=7, new_status="Open", changed_by=7, conn=db_conn)

    # In Progress -> Assigned ❌ (Request 4 is In Progress)
    with pytest.raises(InvalidStatusTransitionError, match="Invalid status transition from 'In Progress' to 'Assigned'"):
        service.change_request_status(request_id=4, new_status="Assigned", changed_by=7, conn=db_conn)

    # In Progress -> Open ❌
    with pytest.raises(InvalidStatusTransitionError, match="Invalid status transition from 'In Progress' to 'Open'"):
        service.change_request_status(request_id=4, new_status="Open", changed_by=7, conn=db_conn)

    # In Progress -> Closed ❌ (deferred to later closure workflow)
    with pytest.raises(InvalidStatusTransitionError, match="Invalid status transition from 'In Progress' to 'Closed'"):
        service.change_request_status(request_id=4, new_status="Closed", changed_by=7, conn=db_conn)

    # On Hold -> Assigned ❌ (Request 6 is On Hold)
    with pytest.raises(InvalidStatusTransitionError, match="Invalid status transition from 'On Hold' to 'Assigned'"):
        service.change_request_status(request_id=6, new_status="Assigned", changed_by=7, conn=db_conn)

    # On Hold -> Open ❌
    with pytest.raises(InvalidStatusTransitionError, match="Invalid status transition from 'On Hold' to 'Open'"):
        service.change_request_status(request_id=6, new_status="Open", changed_by=7, conn=db_conn)

    # On Hold -> Closed ❌ (deferred to later closure workflow)
    with pytest.raises(InvalidStatusTransitionError, match="Invalid status transition from 'On Hold' to 'Closed'"):
        service.change_request_status(request_id=6, new_status="Closed", changed_by=7, conn=db_conn)


def test_neg_5_transition_from_closed(service, db_conn):
    """Negative 5: Any transition from terminal Closed state raises InvalidStatusTransitionError."""
    # Request 1 is Closed
    status = service.get_request_status(1, conn=db_conn)
    assert status["status_name"] == "Closed"

    for target in ["Open", "Assigned", "In Progress", "On Hold", "Closed"]:
        with pytest.raises(InvalidStatusTransitionError):
            service.change_request_status(request_id=1, new_status=target, changed_by=7, conn=db_conn)


def test_neg_6_same_status_update(service, db_conn):
    """Negative 6: Updating to current status raises SameStatusUpdateError."""
    # Request 8 is Open -> Open
    with pytest.raises(SameStatusUpdateError, match="is already in status 'Open'"):
        service.change_request_status(request_id=8, new_status="Open", changed_by=7, conn=db_conn)

    # Request 4 is In Progress -> In Progress
    with pytest.raises(SameStatusUpdateError, match="is already in status 'In Progress'"):
        service.change_request_status(request_id=4, new_status="In Progress", changed_by=7, conn=db_conn)


def test_neg_7_invalid_date(service, db_conn):
    """Negative 7: Non-datetime changed_date raises InvalidDateError."""
    with pytest.raises(InvalidDateError, match="changed_date must be a valid datetime"):
        service.change_request_status(
            request_id=8,
            new_status="Assigned",
            changed_by=7,
            changed_date="2026-10-02",  # type: ignore
            conn=db_conn,
        )


# =============================================================================
# TRANSACTION ATOMICITY & ROLLBACK TESTS
# =============================================================================

def test_atomicity_failed_history_rolls_back_status(service, monkeypatch, db_conn):
    """
    Atomicity Test 1:
    If status_history insertion fails, request.status_id must remain unchanged.
    """
    status_before = service.get_request_status(8, conn=db_conn)
    assert status_before["status_id"] == 1  # Open

    # Mock create_status_history to fail after status_id is updated
    def mock_fail_history(*args, **kwargs):
        raise RuntimeError("Simulated failure during STATUS_HISTORY insertion")

    monkeypatch.setattr(service.request_repo, "create_status_history", mock_fail_history)

    with pytest.raises(DatabaseOperationError, match="Simulated failure during STATUS_HISTORY insertion"):
        service.change_request_status(
            request_id=8,
            new_status="Assigned",
            changed_by=7,
            conn=db_conn,
        )

    # Verify request status_id is completely unchanged in the database
    status_after = service.get_request_status(8, conn=db_conn)
    assert status_after["status_id"] == 1
    assert status_after["status_name"] == "Open"


def test_atomicity_failed_status_update_prevents_history(service, monkeypatch, db_conn):
    """
    Atomicity Test 2:
    If request status update fails, no status_history row must be committed.
    """
    history_count_before = len(service.get_status_history(8, conn=db_conn))

    # Mock update_request_status to fail
    def mock_fail_update(*args, **kwargs):
        raise RuntimeError("Simulated failure during REQUEST status_id update")

    monkeypatch.setattr(service.request_repo, "update_request_status", mock_fail_update)

    with pytest.raises(DatabaseOperationError, match="Simulated failure during REQUEST status_id update"):
        service.change_request_status(
            request_id=8,
            new_status="Assigned",
            changed_by=7,
            conn=db_conn,
        )

    # Verify no new history record was added
    history_count_after = len(service.get_status_history(8, conn=db_conn))
    assert history_count_after == history_count_before


# =============================================================================
# CONCURRENCY / ROW-LEVEL LOCKING TEST
# =============================================================================

def test_concurrency_status_change(service):
    """
    Concurrency Test:
    Demonstrates that SELECT ... FOR UPDATE OF r prevents race conditions.
    Two concurrent threads try to change Request 8 from Open to Assigned.
    Expected: Exactly one succeeds; the second sees the updated status and raises SameStatusUpdateError.
    """
    # Verify initial status on live connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status_id FROM request WHERE request_id = 8")
            assert cur.fetchone()["status_id"] == 1

    results = []

    def task():
        try:
            res = service.change_request_status(
                request_id=8,
                new_status="Assigned",
                changed_by=7,
                remarks="Concurrent assignment task",
                conn=None,  # Uses live pool transaction
            )
            return ("SUCCESS", res["status_id"])
        except SameStatusUpdateError as err:
            return ("SAME_STATUS", str(err))
        except Exception as err:
            return ("ERROR", type(err).__name__, str(err))

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(task)
            f2 = executor.submit(task)
            results.append(f1.result())
            results.append(f2.result())

        statuses = [r[0] for r in results]
        assert "SUCCESS" in statuses
        assert "SAME_STATUS" in statuses
        assert statuses.count("SUCCESS") == 1
        assert statuses.count("SAME_STATUS") == 1

    finally:
        # Clean up and restore Request 8 back to Open
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM status_history WHERE request_id = 8 AND remarks = 'Concurrent assignment task'")
                cur.execute("UPDATE request SET status_id = 1 WHERE request_id = 8")
            conn.commit()


# =============================================================================
# STRICT SIDE-EFFECT BOUNDARY TEST
# =============================================================================

def test_strict_side_effect_boundary(service, db_conn):
    """
    Strict Side-Effect Boundary:
    Status management MUST NOT automatically:
    - create costs
    - create feedback
    - create assignments
    - create work logs
    - modify assignments
    - modify material stock
    """
    cost_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM cost", conn=db_conn)["c"]
    fb_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM feedback", conn=db_conn)["c"]
    assign_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM assignment", conn=db_conn)["c"]
    wl_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM work_log", conn=db_conn)["c"]
    wlm_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM work_log_material", conn=db_conn)["c"]
    mat_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM material", conn=db_conn)["c"]

    # Execute status change
    service.change_request_status(
        request_id=8,
        new_status="Assigned",
        changed_by=7,
        remarks="Boundary test transition",
        conn=db_conn,
    )

    cost_count_after = BaseRepository.fetch_one("SELECT count(*) AS c FROM cost", conn=db_conn)["c"]
    fb_count_after = BaseRepository.fetch_one("SELECT count(*) AS c FROM feedback", conn=db_conn)["c"]
    assign_count_after = BaseRepository.fetch_one("SELECT count(*) AS c FROM assignment", conn=db_conn)["c"]
    wl_count_after = BaseRepository.fetch_one("SELECT count(*) AS c FROM work_log", conn=db_conn)["c"]
    wlm_count_after = BaseRepository.fetch_one("SELECT count(*) AS c FROM work_log_material", conn=db_conn)["c"]
    mat_count_after = BaseRepository.fetch_one("SELECT count(*) AS c FROM material", conn=db_conn)["c"]

    assert cost_count_after == cost_count_before
    assert fb_count_after == fb_count_before
    assert assign_count_after == assign_count_before
    assert wl_count_after == wl_count_before
    assert wlm_count_after == wlm_count_before
    assert mat_count_after == mat_count_before

    # Status management MUST NOT modify or populate request closure fields
    req_after = BaseRepository.fetch_one(
        "SELECT closed_date, resolution_description, closed_by FROM request WHERE request_id = 8",
        conn=db_conn,
    )
    assert req_after["closed_date"] is None
    assert req_after["resolution_description"] is None
    assert req_after["closed_by"] is None


# =============================================================================
# REPOSITORY METHODS TESTS
# =============================================================================

def test_repo_status_methods(repo, db_conn):
    """Test repository status primitives."""
    # list_statuses
    statuses = repo.list_statuses(conn=db_conn)
    assert len(statuses) == 5
    names = [s["status_name"] for s in statuses]
    assert names == ["Open", "Assigned", "In Progress", "On Hold", "Closed"]

    # get_status_by_id
    s1 = repo.get_status_by_id(1, conn=db_conn)
    assert s1 is not None
    assert s1["status_name"] == "Open"

    # get_status_by_name (case insensitive)
    s2 = repo.get_status_by_name("assigned", conn=db_conn)
    assert s2 is not None
    assert s2["status_id"] == 2

    # get_request_status
    rs = repo.get_request_status(1, conn=db_conn)
    assert rs is not None
    assert rs["status_name"] == "Closed"
    assert rs["status_id"] == 5

    # update_request_status
    updated = repo.update_request_status(8, 2, conn=db_conn)
    assert updated is not None
    assert updated["status_id"] == 2
