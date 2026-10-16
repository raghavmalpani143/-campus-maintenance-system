"""
Unit & Integration Tests for RequestRepository
Verifies parameterized SQL execution, relational joins, and database access isolation.
"""

from __future__ import annotations

from datetime import datetime
import pytest

from app.repositories.request import RequestRepository


@pytest.fixture
def repo():
    return RequestRepository()


def test_repo_create_and_get_by_id(repo, db_conn):
    """Test creating a request and retrieving it with all relational joins."""
    req_data = {
        "request_number": "TEST-REQ-REPO-0001",
        "request_date": datetime(2026, 10, 1, 10, 0, 0),
        "description": "Repo test: leaking sink in lab",
        "category_id": 2,  # Plumbing
        "priority_id": 2,  # High
        "requested_by": 1, # Dr. Rajesh Sharma
        "room_id": 1,     # Main Auditorium 101 (Vivekananda Hall)
        "asset_id": None,
        "status_id": 1,   # Open
    }
    created = repo.create_request(req_data, conn=db_conn)
    assert created["request_id"] is not None
    assert created["request_number"] == "TEST-REQ-REPO-0001"

    # Retrieve with joins
    retrieved = repo.get_by_id(created["request_id"], conn=db_conn)
    assert retrieved is not None
    assert retrieved["request_id"] == created["request_id"]
    assert retrieved["request_number"] == "TEST-REQ-REPO-0001"
    assert retrieved["category_name"] == "Plumbing"
    assert retrieved["priority_level"] == "High"
    assert retrieved["status_name"] == "Open"
    assert retrieved["requester_name"] == "Dr. Ramesh Sundaram"
    assert retrieved["room_number"] == "101"
    assert retrieved["building_name"] == "Vivekananda Academic Block"

def test_repo_get_by_request_number(repo, db_conn):
    """Test retrieving existing seeded request by its unique tracking number."""
    req = repo.get_by_request_number("REQ-20260920-0001", conn=db_conn)
    assert req is not None
    assert req["request_number"] == "REQ-20260920-0001"
    assert req["category_name"] == "HVAC"
    assert req["status_name"] == "Closed"
    assert req["building_name"] == "Dr. A.P.J. Abdul Kalam Tech Center"


def test_repo_create_and_fetch_status_history(repo, db_conn):
    """Test creating status history audit entry and retrieving audit trail."""
    req_data = {
        "request_number": "TEST-REQ-REPO-0002",
        "request_date": datetime(2026, 10, 1, 11, 0, 0),
        "description": "Repo test: AC filter cleaning",
        "category_id": 3,
        "priority_id": 3,
        "requested_by": 2,
        "room_id": 2,
        "asset_id": None,
        "status_id": 1,
    }
    created = repo.create_request(req_data, conn=db_conn)
    req_id = created["request_id"]

    history_data = {
        "request_id": req_id,
        "status_id": 1,
        "changed_by": 2,
        "changed_date": datetime(2026, 10, 1, 11, 0, 0),
        "remarks": "Logged via faculty portal",
    }
    history = repo.create_status_history(history_data, conn=db_conn)
    assert history["status_history_id"] is not None

    trail = repo.get_status_history_for_request(req_id, conn=db_conn)
    assert len(trail) == 1
    assert trail[0]["status_name"] == "Open"
    assert trail[0]["changed_by_name"] == "Prof. Ananya Sen"
    assert trail[0]["remarks"] == "Logged via faculty portal"


def test_repo_list_requests_with_filters(repo, db_conn):
    """Test repository listing and filtering capabilities."""
    # List all without filter
    all_requests = repo.list_requests(conn=db_conn)
    assert len(all_requests) >= 10

    # Filter by category_id (HVAC = 3)
    hvac_requests = repo.list_requests({"category_id": 3}, conn=db_conn)
    assert len(hvac_requests) >= 2
    assert all(r["category_name"] == "HVAC" for r in hvac_requests)

    # Filter by priority_id (Critical = 1)
    critical_requests = repo.list_requests({"priority_id": 1}, conn=db_conn)
    assert len(critical_requests) >= 2
    assert all(r["priority_level"] == "Critical" for r in critical_requests)

    # Filter by building_id (Dr. A.P.J. Abdul Kalam Tech Center = 3)
    building_requests = repo.list_requests({"building_id": 3}, conn=db_conn)
    assert len(building_requests) >= 2
    assert all(r["building_name"] == "Dr. A.P.J. Abdul Kalam Tech Center" for r in building_requests)

    # Filter by search string
    search_results = repo.list_requests({"search": "projector"}, conn=db_conn)
    assert len(search_results) >= 1
    assert any("projector" in r["description"].lower() for r in search_results)


def test_repo_update_request_permitted_fields(repo, db_conn):
    """Test updating permitted mutable fields."""
    req_data = {
        "request_number": "TEST-REQ-REPO-0003",
        "request_date": datetime(2026, 10, 1, 12, 0, 0),
        "description": "Initial description",
        "category_id": 1,
        "priority_id": 4,
        "requested_by": 1,
        "room_id": 1,
        "asset_id": None,
        "status_id": 1,
    }
    created = repo.create_request(req_data, conn=db_conn)
    req_id = created["request_id"]

    updates = {
        "description": "Updated issue description with more details",
        "priority_id": 2,  # Escalated to High
    }
    updated = repo.update_request(req_id, updates, conn=db_conn)
    assert updated is not None
    assert updated["description"] == "Updated issue description with more details"
    assert updated["priority_level"] == "High"
    assert updated["priority_id"] == 2


def test_repo_existence_checkers(repo, db_conn):
    """Test lookup helper primitives for users, categories, rooms, assets."""
    assert repo.user_exists(1, conn=db_conn) is True
    assert repo.user_exists(99999, conn=db_conn) is False

    assert repo.category_exists(1, conn=db_conn) is True
    assert repo.category_exists(99999, conn=db_conn) is False

    assert repo.priority_exists(1, conn=db_conn) is True
    assert repo.priority_exists(99999, conn=db_conn) is False

    assert repo.room_exists(1, conn=db_conn) is True
    assert repo.room_exists(99999, conn=db_conn) is False

    asset = repo.get_asset(1, conn=db_conn)
    assert asset is not None
    assert asset["asset_id"] == 1
    assert repo.get_asset(99999, conn=db_conn) is None
