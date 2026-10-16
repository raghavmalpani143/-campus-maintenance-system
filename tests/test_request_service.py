"""
Unit & Integration Tests for RequestService
Covers all Positive, Negative, Transaction Integrity, and Update Guard requirements.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import pytest

from app.exceptions import (
    AssetNotFoundError,
    CategoryNotFoundError,
    DatabaseOperationError,
    DuplicateRequestNumberError,
    ImmutableFieldError,
    InvalidDescriptionError,
    InvalidRequestDateError,
    PriorityNotFoundError,
    RequesterNotFoundError,
    RequestNotFoundError,
    RoomNotFoundError,
    ValidationError,
)
from app.repositories.request import RequestRepository
from app.services.request_service import RequestService


@pytest.fixture
def service():
    return RequestService()


# =============================================================================
# POSITIVE TEST CASES
# =============================================================================

def test_1_create_valid_request(service, db_conn):
    """Positive 1: Create a valid request with automatic request number generation."""
    req = service.create_request(
        description="Flickering fluorescent tube in Room 101",
        category_id=1,  # Electrical
        priority_id=3,  # Medium
        requested_by=1, # Dr. Rajesh Sharma
        room_id=1,     # Room 101
        conn=db_conn,
    )
    assert req is not None
    assert req["request_id"] > 0
    assert req["request_number"].startswith("REQ-")
    assert req["description"] == "Flickering fluorescent tube in Room 101"
    assert req["category_name"] == "Electrical"
    assert req["priority_level"] == "Medium"
    assert req["room_number"] == "101"
    assert req["building_name"] == "Vivekananda Academic Block"


def test_2_verify_request_exists(service, db_conn):
    """Positive 2: Verify created request exists in database."""
    created = service.create_request(
        description="Water fountain pressure is too low",
        category_id=2,  # Plumbing
        priority_id=4,  # Low
        requested_by=3, # Vikramaditya Roy
        room_id=4,     # Room 202
        request_number="TEST-REQ-POS-0002",
        conn=db_conn,
    )
    fetched = service.get_request_by_id(created["request_id"], conn=db_conn)
    assert fetched["request_id"] == created["request_id"]
    assert fetched["request_number"] == "TEST-REQ-POS-0002"


def test_3_verify_status_is_open(service, db_conn):
    """Positive 3: Verify the initial operational status is strictly 'Open' (status_id = 1)."""
    created = service.create_request(
        description="Projector HDMI cable broken",
        category_id=1,
        priority_id=2,
        requested_by=1,
        room_id=1,
        request_number="TEST-REQ-POS-0003",
        conn=db_conn,
    )
    assert created["status_id"] == 1
    assert created["status_name"] == "Open"


def test_4_verify_initial_status_history_row_exists(service, db_conn):
    """Positive 4: Verify the corresponding initial STATUS_HISTORY row exists with Open status."""
    created = service.create_request(
        description="Broken lock on classroom window",
        category_id=4,  # Carpentry & Civil
        priority_id=3,  # Medium
        requested_by=2, # Prof. Ananya Sen
        room_id=3,     # Room 201
        request_number="TEST-REQ-POS-0004",
        remarks="Faculty submitted via office portal",
        conn=db_conn,
    )
    history = service.get_status_history(created["request_id"], conn=db_conn)
    assert len(history) == 1
    entry = history[0]
    assert entry["status_id"] == 1
    assert entry["status_name"] == "Open"
    assert entry["changed_by"] == 2
    assert entry["changed_by_name"] == "Prof. Ananya Sen"
    assert entry["remarks"] == "Faculty submitted via office portal"


def test_5_retrieve_by_request_id(service, db_conn):
    """Positive 5: Retrieve request by primary key ID."""
    req = service.get_request_by_id(1, conn=db_conn)
    assert req["request_id"] == 1
    assert req["request_number"] == "REQ-20260920-0001"
    assert req["category_name"] == "HVAC"
    assert req["status_name"] == "Closed"


def test_6_retrieve_by_request_number(service, db_conn):
    """Positive 6: Retrieve request by unique request tracking number."""
    req = service.get_request_by_number("REQ-20260921-0002", conn=db_conn)
    assert req["request_id"] == 2
    assert req["request_number"] == "REQ-20260921-0002"
    assert req["category_name"] == "Plumbing"


def test_7_list_and_filter_requests(service, db_conn):
    """Positive 7: List and filter requests across various dimensions."""
    # Filter by status_id = 1 (Open)
    open_requests = service.list_requests({"status_id": 1}, conn=db_conn)
    assert len(open_requests) >= 2
    assert all(r["status_name"] == "Open" for r in open_requests)

    # Filter by category_id = 1 (Electrical)
    elec_requests = service.list_requests({"category_id": 1}, conn=db_conn)
    assert len(elec_requests) >= 3
    assert all(r["category_name"] == "Electrical" for r in elec_requests)

    # Filter by priority_id = 1 (Critical)
    crit_requests = service.list_requests({"priority_id": 1}, conn=db_conn)
    assert len(crit_requests) >= 2
    assert all(r["priority_level"] == "Critical" for r in crit_requests)

    # Filter by building_id = 1 (Vivekananda Academic Block)
    building_requests = service.list_requests({"building_id": 1}, conn=db_conn)
    assert len(building_requests) >= 2
    assert all(r["building_name"] == "Vivekananda Academic Block" for r in building_requests)


def test_8_perform_permitted_update(service, db_conn):
    """Positive 8: Perform a permitted update on mutable request fields."""
    created = service.create_request(
        description="Original description of the issue",
        category_id=4,
        priority_id=4,
        requested_by=1,
        room_id=1,
        request_number="TEST-REQ-POS-0008",
        conn=db_conn,
    )
    req_id = created["request_id"]

    updated = service.update_request(
        request_id=req_id,
        updates={
            "description": "Updated clarified description with more details",
            "priority_id": 2,  # Escalated to High
        },
        conn=db_conn,
    )
    assert updated["description"] == "Updated clarified description with more details"
    assert updated["priority_id"] == 2
    assert updated["priority_level"] == "High"


# =============================================================================
# TRANSACTION INTEGRITY TEST
# =============================================================================

def test_transaction_rollback_when_status_history_fails(service, monkeypatch):
    """
    Transaction Integrity: Verify that if the STATUS_HISTORY insertion fails
    after the request insertion, the entire transaction rolls back and no
    partial request row remains in the database.
    """
    test_req_num = "TEST-REQ-ROLLBACK-FAIL"

    # Monkeypatch create_status_history on the repository to simulate unexpected failure
    original_create_status_history = service.request_repo.create_status_history

    def failing_create_status_history(data, conn):
        raise RuntimeError("Simulated status history insertion failure!")

    monkeypatch.setattr(service.request_repo, "create_status_history", failing_create_status_history)

    # Attempt to create request; must raise DatabaseOperationError
    with pytest.raises(DatabaseOperationError, match="Simulated status history insertion failure"):
        service.create_request(
            description="Testing transaction rollback atomicity",
            category_id=1,
            priority_id=1,
            requested_by=1,
            room_id=1,
            request_number=test_req_num,
        )

    # Restore original method to verify database state
    monkeypatch.setattr(service.request_repo, "create_status_history", original_create_status_history)

    # Verify NO partial request exists in the database
    assert service.request_repo.exists_by_request_number(test_req_num) is False
    with pytest.raises(RequestNotFoundError):
        service.get_request_by_number(test_req_num)


# =============================================================================
# NEGATIVE TEST CASES
# =============================================================================

def test_negative_1_missing_or_invalid_description(service, db_conn):
    """Negative 1: Missing or blank description raises InvalidDescriptionError."""
    with pytest.raises(InvalidDescriptionError):
        service.create_request(
            description="",
            category_id=1,
            priority_id=1,
            requested_by=1,
            room_id=1,
            conn=db_conn,
        )

    with pytest.raises(InvalidDescriptionError):
        service.create_request(
            description="   \n\t  ",
            category_id=1,
            priority_id=1,
            requested_by=1,
            room_id=1,
            conn=db_conn,
        )


def test_negative_2_invalid_requester(service, db_conn):
    """Negative 2: Non-existent requester user_id raises RequesterNotFoundError."""
    with pytest.raises(RequesterNotFoundError, match="Requester with user ID 99999 does not exist"):
        service.create_request(
            description="Valid description",
            category_id=1,
            priority_id=1,
            requested_by=99999,
            room_id=1,
            conn=db_conn,
        )


def test_negative_3_invalid_category(service, db_conn):
    """Negative 3: Non-existent category_id raises CategoryNotFoundError."""
    with pytest.raises(CategoryNotFoundError, match="Category with ID 99999 does not exist"):
        service.create_request(
            description="Valid description",
            category_id=99999,
            priority_id=1,
            requested_by=1,
            room_id=1,
            conn=db_conn,
        )


def test_negative_4_invalid_priority(service, db_conn):
    """Negative 4: Non-existent priority_id raises PriorityNotFoundError."""
    with pytest.raises(PriorityNotFoundError, match="Priority with ID 99999 does not exist"):
        service.create_request(
            description="Valid description",
            category_id=1,
            priority_id=99999,
            requested_by=1,
            room_id=1,
            conn=db_conn,
        )


def test_negative_5_invalid_room(service, db_conn):
    """Negative 5: Non-existent room_id raises RoomNotFoundError."""
    with pytest.raises(RoomNotFoundError, match="Room with ID 99999 does not exist"):
        service.create_request(
            description="Valid description",
            category_id=1,
            priority_id=1,
            requested_by=1,
            room_id=99999,
            conn=db_conn,
        )


def test_negative_6_invalid_asset(service, db_conn):
    """Negative 6: Non-existent asset_id or asset in wrong room raises appropriate error."""
    # Asset does not exist
    with pytest.raises(AssetNotFoundError, match="Asset with ID 99999 does not exist"):
        service.create_request(
            description="Valid description",
            category_id=1,
            priority_id=1,
            requested_by=1,
            room_id=1,
            asset_id=99999,
            conn=db_conn,
        )

    # Asset 6 is in room 10 (Aryabhata Data Center), but request specifies room 1 (Vivekananda Auditorium 101)
    with pytest.raises(ValidationError, match="located in room ID 10, not the requested room ID 1"):
        service.create_request(
            description="Valid description",
            category_id=3,
            priority_id=1,
            requested_by=1,
            room_id=1,
            asset_id=6,
            conn=db_conn,
        )


def test_negative_7_duplicate_request_number(service, db_conn):
    """Negative 7: Duplicate request number raises DuplicateRequestNumberError."""
    # REQ-20260920-0001 already exists in seed data
    with pytest.raises(DuplicateRequestNumberError, match="already exists"):
        service.create_request(
            description="Duplicate test",
            category_id=1,
            priority_id=1,
            requested_by=1,
            room_id=1,
            request_number="REQ-20260920-0001",
            conn=db_conn,
        )


def test_negative_8_invalid_request_date(service, db_conn):
    """Negative 8: Future request date raises InvalidRequestDateError."""
    future_date = datetime.now() + timedelta(days=7)
    with pytest.raises(InvalidRequestDateError, match="cannot be in the future"):
        service.create_request(
            description="Future ticket test",
            category_id=1,
            priority_id=1,
            requested_by=1,
            room_id=1,
            request_date=future_date,
            conn=db_conn,
        )


# =============================================================================
# UPDATE BOUNDARY & IMMUTABILITY GUARDS
# =============================================================================

def test_negative_update_immutable_fields(service, db_conn):
    """Verify attempting to update prohibited fields raises ImmutableFieldError."""
    created = service.create_request(
        description="Immutable field guard test",
        category_id=1,
        priority_id=1,
        requested_by=1,
        room_id=1,
        request_number="TEST-REQ-IMMUTABLE-01",
        conn=db_conn,
    )
    req_id = created["request_id"]

    # Attempt to directly modify status_id
    with pytest.raises(ImmutableFieldError, match="status_id"):
        service.update_request(req_id, {"status_id": 5}, conn=db_conn)

    # Attempt to directly modify closed_date or resolution_description
    with pytest.raises(ImmutableFieldError, match="closed_date"):
        service.update_request(req_id, {"closed_date": datetime.now()}, conn=db_conn)

    # Attempt to modify request_number
    with pytest.raises(ImmutableFieldError, match="request_number"):
        service.update_request(req_id, {"request_number": "TAMPERED-NUM"}, conn=db_conn)


def test_negative_update_closed_request(service, db_conn):
    """Verify cannot update attributes of an already Closed request."""
    # Request 1 is Closed in seed data
    with pytest.raises(ValidationError, match="Cannot modify attributes of a Closed"):
        service.update_request(1, {"description": "Try modifying closed ticket"}, conn=db_conn)
