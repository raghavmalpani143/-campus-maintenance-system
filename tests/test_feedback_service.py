"""
Unit, Integration, and Lifecycle Smoke Tests for Feedback Management (Phase 3G)
Covers:
- Positive Feedback Scenarios:
    * Feedback submission on Closed request
    * Minimum rating boundary (1)
    * Maximum rating boundary (5)
    * Comments present (string preservation)
    * Comments omitted / NULL
    * Feedback retrieval by request_id and primary key
    * Service delegation through RequestService
- Negative Validation & Boundary Scenarios:
    * Rejection on Open request
    * Rejection on Assigned request
    * Rejection on In Progress request
    * Rejection on On Hold request
    * Nonexistent request ID
    * Nonexistent user ID
    * Rating below 1 (0, -1)
    * Rating above 5 (6, 10)
    * Non-integer rating types (float, string, bool)
    * Duplicate feedback on same request (1:0..1 constraint)
    * Invalid feedback date (preceding request date or closure date)
- Transaction Atomicity & Rollback:
    * Validation failure rolls back transaction cleanly with zero mutations
- Strict Side-Effect Boundary:
    * Feedback does NOT alter REQUEST.status_id
    * Feedback does NOT modify closure fields
    * Feedback does NOT insert or alter STATUS_HISTORY
    * Feedback does NOT touch assignments, work logs, materials, or costs
- Final Phase 3 End-to-End Smoke Workflow:
    * Full integration lifecycle:
      Create Request -> Assign Technician -> Create Work Log -> Record Material Usage
      -> Record Material Cost -> Change Status -> Close Request -> Record Feedback
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import pytest

from app.db import get_connection
from app.exceptions import (
    DuplicateFeedbackError,
    FeedbackNotFoundError,
    InvalidDateError,
    InvalidRatingError,
    RequestNotClosedError,
    RequestNotFoundError,
    UserNotFoundError,
)
from app.repositories.base import BaseRepository
from app.repositories.feedback import FeedbackRepository
from app.services.assignment_service import AssignmentService
from app.services.feedback_service import FeedbackService
from app.services.material_service import MaterialService
from app.services.request_closure_service import RequestClosureService
from app.services.request_service import RequestService
from app.services.request_status_service import RequestStatusService
from app.services.work_log_service import WorkLogService


@pytest.fixture
def feedback_repo():
    return FeedbackRepository()


@pytest.fixture
def feedback_service(feedback_repo):
    return FeedbackService(feedback_repo=feedback_repo)


@pytest.fixture
def request_service():
    return RequestService()


# =============================================================================
# POSITIVE TESTS
# =============================================================================

def test_pos_1_feedback_on_closed_request(feedback_service, db_conn):
    """Positive 1: Successfully record feedback on Closed Request 10."""
    fb_before = feedback_service.get_feedback_for_request(10, conn=db_conn)
    assert fb_before is None

    fb_date = datetime(2026, 9, 30, 17, 30, 0)
    created = feedback_service.create_feedback(
        request_id=10,
        user_id=5,  # Dr. Vikram Sarabhai
        rating=4,
        comments="Network switch port redundancy configured cleanly.",
        feedback_date=fb_date,
        conn=db_conn,
    )

    assert created["feedback_id"] is not None
    assert created["request_id"] == 10
    assert created["user_id"] == 5
    assert created["rating"] == 4
    assert created["comments"] == "Network switch port redundancy configured cleanly."
    assert created["feedback_date"] == fb_date

    # Verify database persistence
    persisted = feedback_service.get_feedback_for_request(10, conn=db_conn)
    assert persisted is not None
    assert persisted["feedback_id"] == created["feedback_id"]
    assert persisted["rating"] == 4


def test_pos_2_rating_1(feedback_service, db_conn):
    """Positive 2: Minimum rating 1 is valid and recorded."""
    created = feedback_service.create_feedback(
        request_id=10,
        user_id=1,
        rating=1,
        comments="Unsatisfactory response speed.",
        feedback_date=datetime(2026, 9, 30, 18, 0, 0),
        conn=db_conn,
    )
    assert created["rating"] == 1


def test_pos_3_rating_5(feedback_service, db_conn):
    """Positive 3: Maximum rating 5 is valid and recorded."""
    created = feedback_service.create_feedback(
        request_id=10,
        user_id=2,
        rating=5,
        comments="Outstanding repair work!",
        feedback_date=datetime(2026, 9, 30, 18, 0, 0),
        conn=db_conn,
    )
    assert created["rating"] == 5


def test_pos_4_comments_present(feedback_service, db_conn):
    """Positive 4: Comments string is trimmed and preserved."""
    created = feedback_service.create_feedback(
        request_id=10,
        user_id=1,
        rating=4,
        comments="   Technician explained the problem thoroughly.   ",
        feedback_date=datetime(2026, 9, 30, 18, 0, 0),
        conn=db_conn,
    )
    assert created["comments"] == "Technician explained the problem thoroughly."


def test_pos_5_comments_omitted_or_null(feedback_service, db_conn):
    """Positive 5: Comments may be None / omitted."""
    created = feedback_service.create_feedback(
        request_id=10,
        user_id=1,
        rating=4,
        comments=None,
        feedback_date=datetime(2026, 9, 30, 18, 0, 0),
        conn=db_conn,
    )
    assert created["comments"] is None

    retrieved = feedback_service.get_feedback_for_request(10, conn=db_conn)
    assert retrieved["comments"] is None


def test_pos_6_feedback_retrieval(feedback_service, db_conn):
    """Positive 6: Verify retrieval operations for existing seed feedback and new feedback."""
    # Seed feedback for Request 1
    seed_fb = feedback_service.get_feedback_for_request(1, conn=db_conn)
    assert seed_fb is not None
    assert seed_fb["request_id"] == 1
    assert seed_fb["rating"] == 5
    assert seed_fb["user_name"] is not None

    # Retrieve by primary key
    by_pk = feedback_service.get_feedback_by_id(seed_fb["feedback_id"], conn=db_conn)
    assert by_pk["feedback_id"] == seed_fb["feedback_id"]

    # Nonexistent feedback ID raises FeedbackNotFoundError
    with pytest.raises(FeedbackNotFoundError):
        feedback_service.get_feedback_by_id(99999, conn=db_conn)


def test_pos_7_feedback_via_request_service_delegation(request_service, db_conn):
    """Positive 7: RequestService cleanly delegates create_feedback and get_feedback_for_request."""
    created = request_service.create_feedback(
        request_id=10,
        user_id=1,
        rating=5,
        comments="Delegated feedback creation verified.",
        feedback_date=datetime(2026, 9, 30, 18, 0, 0),
        conn=db_conn,
    )
    assert created["rating"] == 5

    fetched = request_service.get_feedback_for_request(10, conn=db_conn)
    assert fetched is not None
    assert fetched["feedback_id"] == created["feedback_id"]


# =============================================================================
# NEGATIVE TESTS
# =============================================================================

def test_neg_1_feedback_on_open_request_rejected(feedback_service, db_conn):
    """Negative 1: Feedback on an Open request (Request 9) must be rejected."""
    with pytest.raises(RequestNotClosedError) as exc_info:
        feedback_service.create_feedback(
            request_id=9,
            user_id=1,
            rating=5,
            conn=db_conn,
        )
    assert "Closed" in str(exc_info.value)
    assert "Open" in str(exc_info.value)


def test_neg_2_feedback_on_assigned_request_rejected(feedback_service, db_conn):
    """Negative 2: Feedback on an Assigned request (Request 7) must be rejected."""
    with pytest.raises(RequestNotClosedError) as exc_info:
        feedback_service.create_feedback(
            request_id=7,
            user_id=1,
            rating=5,
            conn=db_conn,
        )
    assert "Closed" in str(exc_info.value)
    assert "Assigned" in str(exc_info.value)


def test_neg_3_feedback_on_in_progress_request_rejected(feedback_service, db_conn):
    """Negative 3: Feedback on an In Progress request (Request 4) must be rejected."""
    with pytest.raises(RequestNotClosedError) as exc_info:
        feedback_service.create_feedback(
            request_id=4,
            user_id=1,
            rating=5,
            conn=db_conn,
        )
    assert "Closed" in str(exc_info.value)
    assert "In Progress" in str(exc_info.value)


def test_neg_4_feedback_on_on_hold_request_rejected(feedback_service, db_conn):
    """Negative 4: Feedback on an On Hold request (Request 6) must be rejected."""
    with pytest.raises(RequestNotClosedError) as exc_info:
        feedback_service.create_feedback(
            request_id=6,
            user_id=1,
            rating=5,
            conn=db_conn,
        )
    assert "Closed" in str(exc_info.value)
    assert "On Hold" in str(exc_info.value)


def test_neg_5_nonexistent_request(feedback_service, db_conn):
    """Negative 5: Nonexistent request ID must raise RequestNotFoundError."""
    with pytest.raises(RequestNotFoundError):
        feedback_service.create_feedback(
            request_id=99999,
            user_id=1,
            rating=5,
            conn=db_conn,
        )


def test_neg_6_nonexistent_user(feedback_service, db_conn):
    """Negative 6: Nonexistent user ID must raise UserNotFoundError."""
    with pytest.raises(UserNotFoundError):
        feedback_service.create_feedback(
            request_id=10,
            user_id=99999,
            rating=5,
            conn=db_conn,
        )


def test_neg_7_rating_below_1(feedback_service, db_conn):
    """Negative 7: Rating < 1 (0, -1) must raise InvalidRatingError."""
    for invalid_val in [0, -1, -5]:
        with pytest.raises(InvalidRatingError):
            feedback_service.create_feedback(
                request_id=10,
                user_id=1,
                rating=invalid_val,
                conn=db_conn,
            )


def test_neg_8_rating_above_5(feedback_service, db_conn):
    """Negative 8: Rating > 5 (6, 10) must raise InvalidRatingError."""
    for invalid_val in [6, 10, 100]:
        with pytest.raises(InvalidRatingError):
            feedback_service.create_feedback(
                request_id=10,
                user_id=1,
                rating=invalid_val,
                conn=db_conn,
            )


def test_neg_9_rating_invalid_type(feedback_service, db_conn):
    """Negative 9: Non-integer ratings (float, string, bool) must raise InvalidRatingError."""
    for invalid_val in [4.5, "5", True, False, None]:
        with pytest.raises(InvalidRatingError):
            feedback_service.create_feedback(
                request_id=10,
                user_id=1,
                rating=invalid_val,  # type: ignore
                conn=db_conn,
            )


def test_neg_10_duplicate_feedback_rejected(feedback_service, db_conn):
    """Negative 10: Duplicate feedback submission for Request 1 (already has seed feedback)."""
    with pytest.raises(DuplicateFeedbackError) as exc_info:
        feedback_service.create_feedback(
            request_id=1,
            user_id=1,
            rating=4,
            comments="Attempting duplicate feedback",
            conn=db_conn,
        )
    assert "already exists" in str(exc_info.value)


def test_neg_11_invalid_feedback_date(feedback_service, db_conn):
    """Negative 11: Feedback date preceding request date or closure date must be rejected."""
    # Request 10 request_date is '2026-09-30 11:00:00', closed_date is '2026-09-30 16:30:00'
    # Date before request_date
    with pytest.raises(InvalidDateError):
        feedback_service.create_feedback(
            request_id=10,
            user_id=1,
            rating=5,
            feedback_date=datetime(2026, 9, 29, 10, 0, 0),
            conn=db_conn,
        )

    # Date between request_date and closed_date
    with pytest.raises(InvalidDateError):
        feedback_service.create_feedback(
            request_id=10,
            user_id=1,
            rating=5,
            feedback_date=datetime(2026, 9, 30, 12, 0, 0),
            conn=db_conn,
        )


# =============================================================================
# ATOMICITY & ROLLBACK TEST
# =============================================================================

def test_atomicity_failed_feedback_leaves_no_mutations(feedback_service, db_conn):
    """
    Atomicity Test: Validation failure prevents database mutations.
    """
    fb_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM feedback", conn=db_conn)["c"]

    with pytest.raises(InvalidRatingError):
        feedback_service.create_feedback(
            request_id=10,
            user_id=1,
            rating=99,
            conn=db_conn,
        )

    fb_count_after = BaseRepository.fetch_one("SELECT count(*) AS c FROM feedback", conn=db_conn)["c"]
    assert fb_count_after == fb_count_before


# =============================================================================
# STRICT SIDE-EFFECT BOUNDARY TEST
# =============================================================================

def test_strict_side_effect_boundary(feedback_service, db_conn):
    """
    Strict Side-Effect Boundary:
    Creating feedback MUST NOT:
    - alter request status_id
    - alter request closure fields
    - insert or modify status_history
    - modify assignments, work logs, materials, costs, or technicians
    """
    # Snapshot Request 10 state
    req_before = BaseRepository.fetch_one(
        "SELECT status_id, closed_date, resolution_description, closed_by FROM request WHERE request_id = 10",
        conn=db_conn,
    )
    sh_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM status_history WHERE request_id = 10", conn=db_conn)["c"]
    assign_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM assignment", conn=db_conn)["c"]
    wl_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM work_log", conn=db_conn)["c"]
    mat_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM material", conn=db_conn)["c"]
    wlm_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM work_log_material", conn=db_conn)["c"]
    cost_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM cost", conn=db_conn)["c"]
    tech_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM technician", conn=db_conn)["c"]

    # Record feedback
    feedback_service.create_feedback(
        request_id=10,
        user_id=5,
        rating=5,
        comments="Flawless resolution, network connectivity is stable.",
        feedback_date=datetime(2026, 9, 30, 17, 0, 0),
        conn=db_conn,
    )

    # Verify Request 10 remains Closed with identical closure details
    req_after = BaseRepository.fetch_one(
        "SELECT status_id, closed_date, resolution_description, closed_by FROM request WHERE request_id = 10",
        conn=db_conn,
    )
    assert req_after["status_id"] == 5
    assert req_after["closed_date"] == req_before["closed_date"]
    assert req_after["resolution_description"] == req_before["resolution_description"]
    assert req_after["closed_by"] == req_before["closed_by"]

    # Verify status_history was NOT modified
    sh_count_after = BaseRepository.fetch_one("SELECT count(*) AS c FROM status_history WHERE request_id = 10", conn=db_conn)["c"]
    assert sh_count_after == sh_count_before

    # Verify all other tables are completely untouched
    assert BaseRepository.fetch_one("SELECT count(*) AS c FROM assignment", conn=db_conn)["c"] == assign_count_before
    assert BaseRepository.fetch_one("SELECT count(*) AS c FROM work_log", conn=db_conn)["c"] == wl_count_before
    assert BaseRepository.fetch_one("SELECT count(*) AS c FROM material", conn=db_conn)["c"] == mat_count_before
    assert BaseRepository.fetch_one("SELECT count(*) AS c FROM work_log_material", conn=db_conn)["c"] == wlm_count_before
    assert BaseRepository.fetch_one("SELECT count(*) AS c FROM cost", conn=db_conn)["c"] == cost_count_before
    assert BaseRepository.fetch_one("SELECT count(*) AS c FROM technician", conn=db_conn)["c"] == tech_count_before


# =============================================================================
# FINAL PHASE 3 FULL LIFECYCLE SMOKE WORKFLOW
# =============================================================================

def test_final_phase_3_full_lifecycle_smoke_workflow(db_conn):
    """
    Final Phase 3 End-to-End Smoke Workflow:
    Verifies that all Phase 3 modules (3A - 3G) work together smoothly in a complete lifecycle:
      1. Create Request (Phase 3B)
      2. Assign Technician (Phase 3C)
      3. Create Work Log (Phase 3C)
      4. Record Material Usage & Ledger Cost (Phase 3D)
      5. Progress Status: Open -> Assigned -> In Progress (Phase 3E)
      6. Close Request with Resolution Details (Phase 3F)
      7. Record Requester Satisfaction Feedback (Phase 3G)
    """
    req_service = RequestService()
    assign_service = AssignmentService()
    work_log_service = WorkLogService()
    mat_service = MaterialService()
    status_service = RequestStatusService()
    closure_service = RequestClosureService()
    fb_service = FeedbackService()

    # Step 1: Create Maintenance Request (Phase 3B)
    req_date = datetime(2026, 10, 1, 9, 0, 0)
    created_req = req_service.create_request(
        description="Exhaust fan motor emitting high-pitched squeal in Chemistry Lab 101",
        category_id=1,  # Electrical
        priority_id=2,  # High
        requested_by=1,
        room_id=1,      # Lab 101
        request_number="REQ-999999-0001",
        request_date=req_date,
        conn=db_conn,
    )
    req_id = created_req["request_id"]
    assert created_req["status_id"] == 1
    assert created_req["status_name"] == "Open"

    # Step 2: Assign Technician (Phase 3C)
    assign_date = datetime(2026, 10, 1, 9, 30, 0)
    assignment = assign_service.create_assignment(
        request_id=req_id,
        technician_id=1,  # R. Sharma
        assigned_date=assign_date,
        due_date=datetime(2026, 10, 1, 17, 0, 0),
        conn=db_conn,
    )
    assign_id = assignment["assignment_id"]
    assert assignment["assignment_status"] == "Assigned"

    # Step 3: Advance Status to Assigned then In Progress (Phase 3E)
    status_service.change_request_status(
        request_id=req_id,
        new_status="Assigned",
        changed_by=1,
        changed_date=datetime(2026, 10, 1, 9, 35, 0),
        remarks="Technician R. Sharma dispatched",
        conn=db_conn,
    )
    status_service.change_request_status(
        request_id=req_id,
        new_status="In Progress",
        changed_by=1,
        changed_date=datetime(2026, 10, 1, 10, 0, 0),
        remarks="Technician on site inspecting motor bearings",
        conn=db_conn,
    )
    current_status = status_service.get_request_status(req_id, conn=db_conn)
    assert current_status["status_name"] == "In Progress"

    # Step 4: Record Work Log (Phase 3C)
    work_log = work_log_service.create_work_log(
        assignment_id=assign_id,
        work_description="Dismantled motor housing, extracted worn bearings, cleaned stator assembly.",
        hours_spent=Decimal("2.50"),
        work_date=datetime(2026, 10, 1, 11, 0, 0),
        conn=db_conn,
    )
    wl_id = work_log["work_log_id"]
    assert work_log["hours_spent"] == Decimal("2.50")

    # Step 5: Record Material Usage & Deduct Inventory (Phase 3D)
    mat_usage = mat_service.record_material_usage(
        work_log_id=wl_id,
        material_id=1,  # 1.5 sq mm copper wire or bearings
        quantity_used=2,
        issued_by=1,
        conn=db_conn,
    )
    assert mat_usage["cost"] is not None
    assert mat_usage["cost"]["cost_type"] == "Material"

    # Step 6: Close Request with Resolution Details (Phase 3F)
    closure_date = datetime(2026, 10, 1, 14, 0, 0)
    closed_req = closure_service.close_request(
        request_id=req_id,
        closed_by=7,  # Col. Rajesh Nair (Retd)
        resolution_description="Bearings replaced with sealed grade units. Balanced rotor and verified silent operation at 1400 RPM.",
        closed_date=closure_date,
        changed_by=7,
        remarks="Completed and verified in presence of lab technician.",
        conn=db_conn,
    )
    assert closed_req["status_name"] == "Closed"
    assert closed_req["closed_by"] == 7
    assert closed_req["closed_date"] == closure_date

    # Step 7: Record Requester Satisfaction Feedback (Phase 3G)
    feedback_date = datetime(2026, 10, 1, 15, 0, 0)
    feedback = fb_service.create_feedback(
        request_id=req_id,
        user_id=1,  # Requester Manohar Lal
        rating=5,
        comments="Exhaust ventilation runs smoothly and quietly now. Very pleased with prompt resolution!",
        feedback_date=feedback_date,
        conn=db_conn,
    )
    assert feedback["rating"] == 5
    assert feedback["request_id"] == req_id
    assert feedback["comments"] == "Exhaust ventilation runs smoothly and quietly now. Very pleased with prompt resolution!"

    # Verify complete end-to-end status history audit trail
    history = req_service.get_status_history(req_id, conn=db_conn)
    history_statuses = [h["status_name"] for h in history]
    assert history_statuses == ["Open", "Assigned", "In Progress", "Closed"]

    # Verify final request status remains Closed
    final_req = req_service.get_request_by_id(req_id, conn=db_conn)
    assert final_req["status_name"] == "Closed"
    assert final_req["status_id"] == 5
