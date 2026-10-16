"""
Unit, Integration, and Concurrency Tests for Request Closure Management (Phase 3F)
Tests complete workflow for closing maintenance requests:
- Positive transitions: In Progress -> Closed, On Hold -> Closed
- Complete closure field validations: closed_date, resolution_description, closed_by
- Explicit validation of changed_by with no automatic fallback to closed_by
- Negative transitions: Open -> Closed, Assigned -> Closed, Closed -> Closed
- Concurrency safety with row-level locking (FOR UPDATE)
- Transaction atomicity & rollback verification
- Strict side-effect boundaries
"""

from __future__ import annotations

import concurrent.futures
from datetime import datetime
import pytest

from app.db import get_connection
from app.exceptions import (
    AlreadyClosedError,
    DatabaseOperationError,
    InvalidClosureDateError,
    InvalidClosureTransitionError,
    InvalidResolutionDescriptionError,
    RequestNotFoundError,
    UserNotFoundError,
)
from app.repositories.base import BaseRepository
from app.repositories.request import RequestRepository
from app.services.request_closure_service import RequestClosureService
from app.services.request_service import RequestService


@pytest.fixture
def repo():
    return RequestRepository()


@pytest.fixture
def closure_service(repo):
    return RequestClosureService(request_repo=repo)


@pytest.fixture
def request_service(repo):
    return RequestService(request_repo=repo)


# =============================================================================
# POSITIVE TESTS
# =============================================================================

def test_pos_1_in_progress_to_closed(closure_service, db_conn):
    """Positive 1: Successfully close an In Progress request (Request 4)."""
    status_before = RequestRepository().get_request_status(4, conn=db_conn)
    assert status_before["status_name"] == "In Progress"
    assert status_before["status_id"] == 3

    close_dt = datetime(2026, 9, 26, 16, 0, 0)
    updated = closure_service.close_request(
        request_id=4,
        closed_by=7,  # Col. Rajesh Nair (Retd)
        resolution_description="Overhauled pump motor bearings and re-aligned drive shaft.",
        closed_date=close_dt,
        changed_by=7,
        remarks="Completed maintenance ahead of schedule.",
        conn=db_conn,
    )

    # Verify return payload
    assert updated["status_id"] == 5
    assert updated["status_name"] == "Closed"
    assert updated["closed_by"] == 7
    assert updated["closed_date"] == close_dt
    assert updated["resolution_description"] == "Overhauled pump motor bearings and re-aligned drive shaft."
    assert updated["status_history_id"] is not None

    # Verify database state
    req_db = RequestRepository().get_by_id(4, conn=db_conn)
    assert req_db["status_id"] == 5
    assert req_db["status_name"] == "Closed"
    assert req_db["closed_by"] == 7
    assert req_db["closed_date"] == close_dt
    assert req_db["resolution_description"] == "Overhauled pump motor bearings and re-aligned drive shaft."


def test_pos_2_on_hold_to_closed(closure_service, db_conn):
    """Positive 2: Successfully close an On Hold request (Request 6)."""
    status_before = RequestRepository().get_request_status(6, conn=db_conn)
    assert status_before["status_name"] == "On Hold"
    assert status_before["status_id"] == 4

    close_dt = datetime(2026, 9, 28, 11, 45, 0)
    updated = closure_service.close_request(
        request_id=6,
        closed_by=7,
        resolution_description="Replacement 63A breaker installed, load-tested and certified by electrical team.",
        closed_date=close_dt,
        changed_by=7,
        remarks="Electrical panel energized and sealed.",
        conn=db_conn,
    )

    assert updated["status_id"] == 5
    assert updated["status_name"] == "Closed"
    assert updated["closed_by"] == 7
    assert updated["closed_date"] == close_dt
    assert "certified by electrical team" in updated["resolution_description"]

    # Verify live query
    status_after = RequestRepository().get_request_status(6, conn=db_conn)
    assert status_after["status_name"] == "Closed"


def test_pos_3_closure_fields_populated_correctly(closure_service, db_conn):
    """Positive 3: Verify all three closure attributes are populated and readable in request table."""
    close_dt = datetime(2026, 9, 27, 18, 0, 0)
    res_desc = "Replaced 6 burnt-out ballast drivers and tubes across aisles 3 and 4."

    updated = closure_service.close_request(
        request_id=5,  # In Progress
        closed_by=7,
        resolution_description=res_desc,
        closed_date=close_dt,
        changed_by=7,
        conn=db_conn,
    )

    assert updated["closed_date"] == close_dt
    assert updated["resolution_description"] == res_desc
    assert updated["closed_by"] == 7

    raw = BaseRepository.fetch_one(
        "SELECT status_id, closed_date, resolution_description, closed_by FROM request WHERE request_id = 5",
        conn=db_conn,
    )
    assert raw["status_id"] == 5
    assert raw["closed_date"] == close_dt
    assert raw["resolution_description"] == res_desc
    assert raw["closed_by"] == 7


def test_pos_4_single_closed_status_history_row_created(closure_service, db_conn):
    """Positive 4: Exactly one STATUS_HISTORY row is created recording the Closed state."""
    history_before = RequestRepository().get_status_history(4, conn=db_conn)
    count_before = len(history_before)

    close_dt = datetime(2026, 9, 26, 17, 30, 0)
    closure_service.close_request(
        request_id=4,
        closed_by=7,
        resolution_description="Filter media backwashed and pressure sensors recalibrated.",
        closed_date=close_dt,
        changed_by=7,
        remarks="Verified operational flow rate.",
        conn=db_conn,
    )

    history_after = RequestRepository().get_status_history(4, conn=db_conn)
    assert len(history_after) == count_before + 1

    latest = history_after[-1]
    assert latest["request_id"] == 4
    assert latest["status_id"] == 5
    assert latest["status_name"] == "Closed"
    assert latest["changed_by"] == 7
    assert latest["changed_date"] == close_dt
    assert latest["remarks"] == "Verified operational flow rate."


def test_pos_5_distinct_closed_by_and_changed_by_no_fallback(closure_service, db_conn):
    """
    Positive 5: Verify distinct closed_by and changed_by are stored in their respective tables.
    closed_by (User 7 - Manager) -> request.closed_by
    changed_by (User 4 - Arunachalam P., Technician) -> status_history.changed_by
    Confirms no silent fallback or substitution occurs between the two fields.
    """
    close_dt = datetime(2026, 9, 26, 18, 0, 0)
    res = closure_service.close_request(
        request_id=4,
        closed_by=7,
        resolution_description="Supervisory sign-off after technician inspection.",
        closed_date=close_dt,
        changed_by=4,
        remarks="Technician recorded closure on supervisor approval.",
        conn=db_conn,
    )

    # In request table: closed_by must be 7
    raw_req = BaseRepository.fetch_one(
        "SELECT closed_by FROM request WHERE request_id = 4",
        conn=db_conn,
    )
    assert raw_req["closed_by"] == 7

    # In status_history table: changed_by must be 4
    history = RequestRepository().get_status_history(4, conn=db_conn)
    latest = history[-1]
    assert latest["changed_by"] == 4
    assert latest["changed_by_name"] == "Priya Sharma"
    assert latest["status_id"] == 5


def test_pos_6_closure_via_request_service_delegation(request_service, db_conn):
    """Positive 6: RequestService.close_request delegates to RequestClosureService seamlessly."""
    close_dt = datetime(2026, 9, 27, 9, 0, 0)
    res = request_service.close_request(
        request_id=4,
        closed_by=7,
        resolution_description="Delegation test: resolved motor vibration.",
        closed_date=close_dt,
        changed_by=7,
        conn=db_conn,
    )
    assert res["status_name"] == "Closed"
    assert res["status_id"] == 5


# =============================================================================
# NEGATIVE VALIDATION TESTS
# =============================================================================

def test_neg_1_nonexistent_request(closure_service, db_conn):
    """Negative 1: Nonexistent request ID raises RequestNotFoundError."""
    with pytest.raises(RequestNotFoundError, match="Request with ID 99999 does not exist"):
        closure_service.close_request(
            request_id=99999,
            closed_by=7,
            resolution_description="Valid resolution description.",
            closed_date=datetime(2026, 9, 26, 10, 0, 0),
            changed_by=7,
            conn=db_conn,
        )


def test_neg_2_nonexistent_closed_by_user(closure_service, db_conn):
    """Negative 2: Nonexistent closed_by user raises UserNotFoundError."""
    with pytest.raises(UserNotFoundError, match="User with ID 99999 does not exist"):
        closure_service.close_request(
            request_id=4,
            closed_by=99999,
            resolution_description="Valid resolution description.",
            closed_date=datetime(2026, 9, 26, 10, 0, 0),
            changed_by=7,
            conn=db_conn,
        )


def test_neg_3_invalid_closed_by_values(closure_service, db_conn):
    """Negative 3: Missing, negative, or invalid closed_by raises UserNotFoundError."""
    with pytest.raises(UserNotFoundError, match="closed_by user ID must be a positive integer"):
        closure_service.close_request(
            request_id=4,
            closed_by=None,  # type: ignore
            resolution_description="Valid resolution description.",
            closed_date=datetime(2026, 9, 26, 10, 0, 0),
            changed_by=7,
            conn=db_conn,
        )

    with pytest.raises(UserNotFoundError, match="closed_by user ID must be a positive integer"):
        closure_service.close_request(
            request_id=4,
            closed_by=-5,
            resolution_description="Valid resolution description.",
            closed_date=datetime(2026, 9, 26, 10, 0, 0),
            changed_by=7,
            conn=db_conn,
        )


def test_neg_4_missing_or_invalid_changed_by(closure_service, db_conn):
    """Negative 4: Missing, None, or invalid changed_by raises UserNotFoundError (no silent fallback)."""
    close_dt = datetime(2026, 9, 26, 10, 0, 0)

    # Missing None changed_by
    with pytest.raises(UserNotFoundError, match="changed_by user ID must be a positive integer"):
        closure_service.close_request(
            request_id=4,
            closed_by=7,
            resolution_description="Valid resolution description.",
            closed_date=close_dt,
            changed_by=None,  # type: ignore
            conn=db_conn,
        )

    # Negative changed_by
    with pytest.raises(UserNotFoundError, match="changed_by user ID must be a positive integer"):
        closure_service.close_request(
            request_id=4,
            closed_by=7,
            resolution_description="Valid resolution description.",
            closed_date=close_dt,
            changed_by=-1,
            conn=db_conn,
        )


def test_neg_5_nonexistent_changed_by_user(closure_service, db_conn):
    """Negative 5: Explicitly passing a nonexistent changed_by user ID raises UserNotFoundError."""
    close_dt = datetime(2026, 9, 26, 10, 0, 0)
    with pytest.raises(UserNotFoundError, match="User with ID 99999 does not exist"):
        closure_service.close_request(
            request_id=4,
            closed_by=7,
            resolution_description="Valid resolution description.",
            closed_date=close_dt,
            changed_by=99999,
            conn=db_conn,
        )


def test_neg_6_empty_or_whitespace_resolution_description(closure_service, db_conn):
    """Negative 6: Missing, empty, or whitespace resolution_description raises InvalidResolutionDescriptionError."""
    close_dt = datetime(2026, 9, 26, 10, 0, 0)

    # Empty string
    with pytest.raises(InvalidResolutionDescriptionError, match="resolution_description must be present and non-empty"):
        closure_service.close_request(
            request_id=4,
            closed_by=7,
            resolution_description="",
            closed_date=close_dt,
            changed_by=7,
            conn=db_conn,
        )

    # Whitespace only
    with pytest.raises(InvalidResolutionDescriptionError, match="resolution_description must be present and non-empty"):
        closure_service.close_request(
            request_id=4,
            closed_by=7,
            resolution_description="   \n\t  ",
            closed_date=close_dt,
            changed_by=7,
            conn=db_conn,
        )

    # None value
    with pytest.raises(InvalidResolutionDescriptionError, match="resolution_description must be present and non-empty"):
        closure_service.close_request(
            request_id=4,
            closed_by=7,
            resolution_description=None,  # type: ignore
            closed_date=close_dt,
            changed_by=7,
            conn=db_conn,
        )


def test_neg_7_missing_or_invalid_closure_date(closure_service, db_conn):
    """Negative 7: Missing (None) or non-datetime closed_date raises InvalidClosureDateError."""
    # Omitted / None closed_date
    with pytest.raises(InvalidClosureDateError, match="closed_date must be provided"):
        closure_service.close_request(
            request_id=4,
            closed_by=7,
            resolution_description="Valid resolution description.",
            closed_date=None,  # type: ignore
            changed_by=7,
            conn=db_conn,
        )

    # Non-datetime type
    with pytest.raises(InvalidClosureDateError, match="closed_date must be provided"):
        closure_service.close_request(
            request_id=4,
            closed_by=7,
            resolution_description="Valid resolution description.",
            closed_date="2026-09-26",  # type: ignore
            changed_by=7,
            conn=db_conn,
        )


def test_neg_8_closure_date_preceding_request_date(closure_service, db_conn):
    """Negative 8: closed_date preceding request_date raises InvalidClosureDateError."""
    # Request 4 request_date is 2026-09-25 11:20:00
    past_date = datetime(2026, 9, 20, 10, 0, 0)
    with pytest.raises(InvalidClosureDateError, match="cannot precede request_date"):
        closure_service.close_request(
            request_id=4,
            closed_by=7,
            resolution_description="Valid resolution description.",
            closed_date=past_date,
            changed_by=7,
            conn=db_conn,
        )


def test_neg_9_open_to_closed_rejected(closure_service, db_conn):
    """Negative 9: Attempting to close an Open request (Request 8) raises InvalidClosureTransitionError."""
    status = RequestRepository().get_request_status(8, conn=db_conn)
    assert status["status_name"] == "Open"

    with pytest.raises(InvalidClosureTransitionError, match="Cannot close request 8 from status 'Open'"):
        closure_service.close_request(
            request_id=8,
            closed_by=7,
            resolution_description="Attempted premature closure on open request.",
            closed_date=datetime(2026, 9, 30, 10, 0, 0),
            changed_by=7,
            conn=db_conn,
        )


def test_neg_10_assigned_to_closed_rejected(closure_service, db_conn):
    """Negative 10: Attempting to close an Assigned request (Request 7) raises InvalidClosureTransitionError."""
    status = RequestRepository().get_request_status(7, conn=db_conn)
    assert status["status_name"] == "Assigned"

    with pytest.raises(InvalidClosureTransitionError, match="Cannot close request 7 from status 'Assigned'"):
        closure_service.close_request(
            request_id=7,
            closed_by=7,
            resolution_description="Attempted premature closure on assigned request.",
            closed_date=datetime(2026, 9, 30, 10, 0, 0),
            changed_by=7,
            conn=db_conn,
        )


def test_neg_11_already_closed_request_rejected(closure_service, db_conn):
    """Negative 11: Attempting to close an already Closed request (Request 1) raises AlreadyClosedError."""
    status = RequestRepository().get_request_status(1, conn=db_conn)
    assert status["status_name"] == "Closed"

    with pytest.raises(AlreadyClosedError, match="Request 1 is already Closed"):
        closure_service.close_request(
            request_id=1,
            closed_by=7,
            resolution_description="Attempted re-closure.",
            closed_date=datetime(2026, 9, 30, 10, 0, 0),
            changed_by=7,
            conn=db_conn,
        )


# =============================================================================
# ATOMICITY & ROLLBACK TESTS
# =============================================================================

def test_atomicity_failed_request_update_leaves_no_history(closure_service, monkeypatch, db_conn):
    """
    Atomicity 1: If request update fails, no status_history row is inserted
    and the request retains its original In Progress status and NULL closure fields.
    """
    status_before = RequestRepository().get_request_status(4, conn=db_conn)
    assert status_before["status_name"] == "In Progress"
    history_count_before = len(RequestRepository().get_status_history(4, conn=db_conn))

    def mock_fail_close(*args, **kwargs):
        raise RuntimeError("Simulated failure during request closure UPDATE")

    monkeypatch.setattr(closure_service.request_repo, "close_request", mock_fail_close)

    with pytest.raises(DatabaseOperationError, match="Simulated failure during request closure UPDATE"):
        closure_service.close_request(
            request_id=4,
            closed_by=7,
            resolution_description="Valid description.",
            closed_date=datetime(2026, 9, 26, 12, 0, 0),
            changed_by=7,
            conn=db_conn,
        )

    # Verify request table is unchanged
    req_after = BaseRepository.fetch_one(
        "SELECT status_id, closed_date, resolution_description, closed_by FROM request WHERE request_id = 4",
        conn=db_conn,
    )
    assert req_after["status_id"] == 3
    assert req_after["closed_date"] is None
    assert req_after["resolution_description"] is None
    assert req_after["closed_by"] is None

    # Verify status_history is unchanged
    history_count_after = len(RequestRepository().get_status_history(4, conn=db_conn))
    assert history_count_after == history_count_before


def test_atomicity_failed_history_insert_rolls_back_closure(closure_service, monkeypatch, db_conn):
    """
    Atomicity 2: If status_history insertion fails, request closure fields
    and status_id rollback to original state completely.
    """
    status_before = RequestRepository().get_request_status(4, conn=db_conn)
    assert status_before["status_name"] == "In Progress"
    history_count_before = len(RequestRepository().get_status_history(4, conn=db_conn))

    def mock_fail_history(*args, **kwargs):
        raise RuntimeError("Simulated failure during STATUS_HISTORY insertion on closure")

    monkeypatch.setattr(closure_service.request_repo, "create_status_history", mock_fail_history)

    with pytest.raises(DatabaseOperationError, match="Simulated failure during STATUS_HISTORY insertion on closure"):
        closure_service.close_request(
            request_id=4,
            closed_by=7,
            resolution_description="Valid description.",
            closed_date=datetime(2026, 9, 26, 12, 0, 0),
            changed_by=7,
            conn=db_conn,
        )

    # Verify request table was rolled back and is NOT Closed
    req_after = BaseRepository.fetch_one(
        "SELECT status_id, closed_date, resolution_description, closed_by FROM request WHERE request_id = 4",
        conn=db_conn,
    )
    assert req_after["status_id"] == 3
    assert req_after["closed_date"] is None
    assert req_after["resolution_description"] is None
    assert req_after["closed_by"] is None

    # Verify history count is unchanged
    history_count_after = len(RequestRepository().get_status_history(4, conn=db_conn))
    assert history_count_after == history_count_before


def test_atomicity_validation_failure_causes_no_database_mutation(closure_service, db_conn):
    """
    Atomicity 3: If validation fails before SQL update, no changes occur in the database.
    """
    history_count_before = len(RequestRepository().get_status_history(4, conn=db_conn))

    # Trigger validation failure (invalid closed_date preceding request_date)
    with pytest.raises(InvalidClosureDateError):
        closure_service.close_request(
            request_id=4,
            closed_by=7,
            resolution_description="Valid description.",
            closed_date=datetime(2020, 1, 1),
            changed_by=7,
            conn=db_conn,
        )

    req_after = BaseRepository.fetch_one(
        "SELECT status_id, closed_date, resolution_description, closed_by FROM request WHERE request_id = 4",
        conn=db_conn,
    )
    assert req_after["status_id"] == 3
    assert req_after["closed_date"] is None

    history_count_after = len(RequestRepository().get_status_history(4, conn=db_conn))
    assert history_count_after == history_count_before


# =============================================================================
# CONCURRENCY TEST
# =============================================================================

def test_concurrency_closure_serializes_with_row_lock(closure_service):
    """
    Concurrency Test:
    Demonstrates that SELECT ... FOR UPDATE serializes concurrent closure attempts.
    Two concurrent threads attempt to close Request 5 simultaneously.
    Expected: Exactly one succeeds; the second sees the newly committed Closed state and raises AlreadyClosedError.
    """
    # Verify initial status on live connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status_id FROM request WHERE request_id = 5")
            assert cur.fetchone()["status_id"] == 3  # In Progress

    close_dt = datetime(2026, 9, 27, 15, 0, 0)
    results = []

    def task(thread_id: int):
        try:
            res = closure_service.close_request(
                request_id=5,
                closed_by=7,
                resolution_description=f"Thread {thread_id} completed resolution.",
                closed_date=close_dt,
                changed_by=7,
                remarks=f"Concurrent closure thread {thread_id}",
                conn=None,  # Uses live pool transaction
            )
            return ("SUCCESS", res["status_id"])
        except AlreadyClosedError as err:
            return ("ALREADY_CLOSED", str(err))
        except Exception as err:
            return ("ERROR", type(err).__name__, str(err))

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(task, 1)
            f2 = executor.submit(task, 2)
            results.append(f1.result())
            results.append(f2.result())

        statuses = [r[0] for r in results]
        assert "SUCCESS" in statuses
        assert "ALREADY_CLOSED" in statuses
        assert statuses.count("SUCCESS") == 1
        assert statuses.count("ALREADY_CLOSED") == 1

    finally:
        # Clean up and restore Request 5 back to In Progress
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM status_history WHERE request_id = 5 AND remarks LIKE 'Concurrent closure thread%'")
                cur.execute("UPDATE request SET status_id = 3, closed_date = NULL, resolution_description = NULL, closed_by = NULL WHERE request_id = 5")
            conn.commit()


# =============================================================================
# STRICT SIDE-EFFECT BOUNDARY TEST
# =============================================================================

def test_strict_side_effect_boundary(closure_service, db_conn):
    """
    Strict Side-Effect Boundary:
    Closing a request MUST NOT automatically:
    - create costs
    - create feedback
    - create or modify assignments
    - create work logs
    - modify material stock or usage
    - modify technicians
    """
    cost_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM cost", conn=db_conn)["c"]
    fb_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM feedback", conn=db_conn)["c"]
    assign_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM assignment", conn=db_conn)["c"]
    wl_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM work_log", conn=db_conn)["c"]
    wlm_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM work_log_material", conn=db_conn)["c"]
    mat_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM material", conn=db_conn)["c"]
    tech_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM technician", conn=db_conn)["c"]

    # Execute closure
    closure_service.close_request(
        request_id=4,
        closed_by=7,
        resolution_description="Boundary test closure: verified zero side effects on unrelated tables.",
        closed_date=datetime(2026, 9, 26, 15, 0, 0),
        changed_by=7,
        conn=db_conn,
    )

    cost_count_after = BaseRepository.fetch_one("SELECT count(*) AS c FROM cost", conn=db_conn)["c"]
    fb_count_after = BaseRepository.fetch_one("SELECT count(*) AS c FROM feedback", conn=db_conn)["c"]
    assign_count_after = BaseRepository.fetch_one("SELECT count(*) AS c FROM assignment", conn=db_conn)["c"]
    wl_count_after = BaseRepository.fetch_one("SELECT count(*) AS c FROM work_log", conn=db_conn)["c"]
    wlm_count_after = BaseRepository.fetch_one("SELECT count(*) AS c FROM work_log_material", conn=db_conn)["c"]
    mat_count_after = BaseRepository.fetch_one("SELECT count(*) AS c FROM material", conn=db_conn)["c"]
    tech_count_after = BaseRepository.fetch_one("SELECT count(*) AS c FROM technician", conn=db_conn)["c"]

    assert cost_count_after == cost_count_before
    assert fb_count_after == fb_count_before
    assert assign_count_after == assign_count_before
    assert wl_count_after == wl_count_before
    assert wlm_count_after == wlm_count_before
    assert mat_count_after == mat_count_before
    assert tech_count_after == tech_count_before
