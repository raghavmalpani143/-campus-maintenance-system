"""
Phase 4 Integration and Feature Tests
Validates:
1. Technician Incoming/Unassigned Requests & Isolation
2. All Six Technician Accounts and Department Scoping
3. User Self-Registration (Student, Faculty, Staff) and Invariants
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import get_connection
from app.server import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_phase4_data():
    """Ensure all test-generated users and requests are cleanly purged."""
    yield
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Delete status history and requests created by tests
            cur.execute("""
                DELETE FROM status_history 
                WHERE request_id IN (
                    SELECT request_id FROM request 
                    WHERE request_number LIKE 'REQ-9999%' 
                       OR request_number LIKE 'TEST-%'
                       OR description LIKE 'TEST-PHASE4%'
                );
            """)
            cur.execute("""
                DELETE FROM request 
                WHERE request_number LIKE 'REQ-9999%' 
                   OR request_number LIKE 'TEST-%'
                   OR description LIKE 'TEST-PHASE4%';
            """)
            # Delete test users
            cur.execute("""
                DELETE FROM "user" 
                WHERE email LIKE 'test.%@example.com' 
                   OR email LIKE 'phase4.%@example.com';
            """)
        conn.commit()


# =============================================================================
# PROBLEM 1 & 2: TECHNICIAN REAL-TIME VISIBILITY & ACCOUNTS
# =============================================================================

def test_electrical_request_created_and_visible_to_electrical_technician(client):
    """
    1. Requester creates Electrical request.
    2. Electrical technician dashboard sees it as incoming/unassigned with populated fields.
    """
    req_res = client.post("/api/requests", json={
        "category_id": 1,  # Electrical
        "priority_id": 2,  # High
        "room_id": 14,
        "requested_by": 4,  # Priya Sharma
        "description": "TEST-PHASE4: Circuit breaker tripped in computer lab",
    })
    assert req_res.status_code == 201
    created = req_res.json()
    new_req_id = created["request_id"]
    req_num = created["request_number"]

    # 2. Electrical technician (ID 1 - Mahesh Chandra) dashboard
    tech_dash = client.get("/api/technician/1/dashboard")
    assert tech_dash.status_code == 200
    dash_data = tech_dash.json()

    assert "incoming_requests" in dash_data
    incoming = dash_data["incoming_requests"]
    assert any(r["request_id"] == new_req_id for r in incoming)

    matched = next(r for r in incoming if r["request_id"] == new_req_id)
    assert matched["request_number"] == req_num
    assert matched["category_name"] == "Electrical"
    assert matched["status_name"] == "Open"
    assert matched["priority_level"] == "High"
    assert matched["requester_name"] == "Priya Sharma"
    assert matched["building_name"] is not None
    assert matched["room_number"] is not None
    assert matched["assignment_id"] is None


def test_technician_dashboard_does_not_show_unrelated_category_requests(client):
    """
    3. Technician dashboard does not show unrelated category requests.
    When Electrical request is created, Plumbing & HVAC technicians do not see it.
    """
    req_res = client.post("/api/requests", json={
        "category_id": 1,  # Electrical
        "priority_id": 3,  # Medium
        "room_id": 1,
        "requested_by": 4,
        "description": "TEST-PHASE4: Fluorescent ballast buzzing",
    })
    assert req_res.status_code == 201
    new_req_id = req_res.json()["request_id"]

    # Plumbing technician (ID 2 - Dinesh Kumar Verma)
    plumb_dash = client.get("/api/technician/2/dashboard").json()
    assert not any(r["request_id"] == new_req_id for r in plumb_dash["incoming_requests"])

    # HVAC technician (ID 3 - Gurpreet Singh)
    hvac_dash = client.get("/api/technician/3/dashboard").json()
    assert not any(r["request_id"] == new_req_id for r in hvac_dash["incoming_requests"])


def test_existing_assigned_work_still_appears(client):
    """
    4. Existing assigned work still appears under My Work Orders (assignments).
    """
    tech_res = client.get("/api/technician/3/dashboard")
    assert tech_res.status_code == 200
    data = tech_res.json()

    assert len(data["assignments"]) > 0
    assert any(a["technician_id"] == 3 for a in data["assignments"])
    assert data["counts"]["total_assignments"] >= len(data["assignments"])


def test_another_technician_assignment_remains_invisible(client):
    """
    5. Another technician's private assigned work order remains invisible.
    """
    tech1_data = client.get("/api/technician/1/dashboard").json()
    tech2_data = client.get("/api/technician/2/dashboard").json()

    tech1_assignment_ids = {a["assignment_id"] for a in tech1_data["assignments"]}
    tech2_assignment_ids = {a["assignment_id"] for a in tech2_data["assignments"]}

    assert tech1_assignment_ids.isdisjoint(tech2_assignment_ids)


def test_new_request_appears_after_dashboard_refresh_poll(client):
    """
    6. New request appears after dashboard refresh/poll.
    Simulates near-real-time polling behavior.
    """
    dash_before = client.get("/api/technician/1/dashboard").json()
    initial_count = dash_before["counts"]["incoming_requests"]

    req_res = client.post("/api/requests", json={
        "category_id": 1,
        "priority_id": 1,  # Critical
        "room_id": 2,
        "requested_by": 4,
        "description": "TEST-PHASE4: Main switchboard sparks",
    })
    assert req_res.status_code == 201
    new_id = req_res.json()["request_id"]

    dash_after = client.get("/api/technician/1/dashboard").json()
    assert dash_after["counts"]["incoming_requests"] == initial_count + 1
    assert any(r["request_id"] == new_id for r in dash_after["incoming_requests"])


def test_all_six_technician_accounts_are_returned(client):
    """
    7. All six technician accounts are returned from /api/auth/demo-accounts dynamically.
    """
    res = client.get("/api/auth/demo-accounts")
    assert res.status_code == 200
    accounts = res.json()

    technicians = [a for a in accounts if a["portal_role"] == "technician"]
    assert len(technicians) >= 6

    dept_names = {t["department"] for t in technicians}
    # Must cover all 6 operational areas
    assert any("Civil" in d or "Carpentry" in d for d in dept_names)
    assert any("Electrical" in d for d in dept_names)
    assert any("HVAC" in d for d in dept_names)
    assert any("Laboratory" in d for d in dept_names)
    assert any("Network" in d for d in dept_names)
    assert any("Plumbing" in d for d in dept_names)


def test_plumbing_technician_login_works(client):
    """
    8. Plumbing technician login works and returns correct portal role & department.
    """
    res = client.post("/api/auth/demo-login", json={"email": "dinesh.tech@campus.edu"})
    assert res.status_code == 200
    user = res.json()

    assert user["entity_type"] == "technician"
    assert user["portal_role"] == "technician"
    assert user["full_name"] == "Dinesh Kumar Verma"
    assert "Plumbing" in user["department"]
    assert user["technician_id"] == 2


def test_each_technician_gets_correct_department_category_scope(client):
    """
    9. Each technician gets correct department/category scope for incoming requests.
    """
    from app.services.technician_service import TechnicianService

    service = TechnicianService()
    assert service.map_department_to_category("Electrical Maintenance") == "Electrical"
    assert service.map_department_to_category("Plumbing & Hydraulics") == "Plumbing"
    assert service.map_department_to_category("HVAC & Refrigeration") == "HVAC"
    assert service.map_department_to_category("Civil & Carpentry") == "Carpentry & Civil"
    assert service.map_department_to_category("Network Infrastructure") == "Network & IT Infrastructure"
    assert service.map_department_to_category("Laboratory Utilities") == "Laboratory Utilities"


# =============================================================================
# PROBLEM 3: REGISTRATION & SELF-SERVICE IDENTITY TESTS
# =============================================================================

def test_student_registration_succeeds(client):
    """1. Student registration succeeds."""
    res = client.post("/api/auth/register", json={
        "full_name": "Test Student User",
        "email": "test.student@example.com",
        "phone": "+91 99999 11111",
        "account_type": "Student",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["full_name"] == "Test Student User"
    assert data["email"] == "test.student@example.com"
    assert data["role_name"] == "Student"
    assert data["portal_role"] == "requester"
    assert data["status"] == "Active"
    assert "user_id" in data


def test_faculty_registration_succeeds(client):
    """2. Faculty registration succeeds."""
    res = client.post("/api/auth/register", json={
        "full_name": "Test Faculty Member",
        "email": "test.faculty@example.com",
        "phone": "+91 99999 22222",
        "account_type": "Faculty",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["role_name"] == "Faculty"
    assert data["portal_role"] == "requester"


def test_staff_registration_succeeds(client):
    """3. Staff registration succeeds."""
    res = client.post("/api/auth/register", json={
        "full_name": "Test Staff Officer",
        "email": "test.staff@example.com",
        "phone": "+91 99999 33333",
        "account_type": "Staff",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["role_name"] == "Staff"
    assert data["portal_role"] == "requester"


def test_duplicate_email_rejected(client):
    """4. Duplicate email rejected with clean user-facing error."""
    # Existing seed user email
    res = client.post("/api/auth/register", json={
        "full_name": "Another Priya",
        "email": "priya.sharma@campus.edu",
        "account_type": "Student",
    })
    assert res.status_code == 400
    data = res.json()
    assert "An account with this email already exists." in data["message"]


def test_missing_name_rejected(client):
    """5. Missing name rejected."""
    res = client.post("/api/auth/register", json={
        "full_name": "",
        "email": "test.noname@example.com",
        "account_type": "Student",
    })
    assert res.status_code == 400
    assert "Full Name is required" in res.json()["message"]


def test_missing_email_rejected(client):
    """6. Missing email rejected."""
    res = client.post("/api/auth/register", json={
        "full_name": "No Email",
        "email": "   ",
        "account_type": "Student",
    })
    assert res.status_code == 400
    assert "Email is required" in res.json()["message"]


def test_invalid_email_rejected(client):
    """7. Invalid email rejected."""
    res = client.post("/api/auth/register", json={
        "full_name": "Invalid Email User",
        "email": "not-an-email-address",
        "account_type": "Student",
    })
    assert res.status_code == 400
    assert "Invalid email format" in res.json()["message"]


def test_invalid_account_type_rejected(client):
    """8. Invalid account type rejected."""
    res = client.post("/api/auth/register", json={
        "full_name": "Invalid Role User",
        "email": "test.badrole@example.com",
        "account_type": "Administrator",
    })
    assert res.status_code == 400
    assert "Invalid account type" in res.json()["message"]


def test_technician_self_registration_rejected(client):
    """9. Technician self-registration rejected."""
    res = client.post("/api/auth/register", json={
        "full_name": "Rogue Technician",
        "email": "test.techreg@example.com",
        "account_type": "Technician",
    })
    assert res.status_code == 400
    assert "Self-registration is not permitted" in res.json()["message"]


def test_facility_manager_self_registration_rejected(client):
    """10. Facility Manager self-registration rejected."""
    res = client.post("/api/auth/register", json={
        "full_name": "Fake Facility Manager",
        "email": "test.fmreg@example.com",
        "account_type": "Facility Manager",
    })
    assert res.status_code == 400
    assert "Self-registration is not permitted" in res.json()["message"]


def test_newly_registered_user_can_login(client):
    """11. Newly registered user can log in via registered email."""
    reg = client.post("/api/auth/register", json={
        "full_name": "Registered Student A",
        "email": "test.student.a@example.com",
        "account_type": "Student",
    })
    assert reg.status_code == 201

    login_res = client.post("/api/auth/demo-login", json={
        "email": "test.student.a@example.com"
    })
    assert login_res.status_code == 200
    user = login_res.json()
    assert user["email"] == "test.student.a@example.com"
    assert user["portal_role"] == "requester"
    assert user["user_id"] == reg.json()["user_id"]


def test_newly_registered_user_can_create_request(client):
    """12. Newly registered user can create a request."""
    reg = client.post("/api/auth/register", json={
        "full_name": "Registered Student B",
        "email": "test.student.b@example.com",
        "account_type": "Student",
    })
    assert reg.status_code == 201
    user_id = reg.json()["user_id"]

    req_res = client.post("/api/requests", json={
        "category_id": 2,  # Plumbing
        "priority_id": 3,
        "room_id": 14,
        "requested_by": user_id,
        "description": "TEST-PHASE4: Washbasin faucet dripping continuously",
    })
    assert req_res.status_code == 201
    req_data = req_res.json()
    assert req_data["requested_by"] == user_id
    assert req_data["status_name"] == "Open"


def test_newly_registered_user_only_sees_their_own_requests(client):
    """13. Newly registered user only sees their own requests."""
    reg1 = client.post("/api/auth/register", json={
        "full_name": "User One",
        "email": "test.user1@example.com",
        "account_type": "Student",
    }).json()

    reg2 = client.post("/api/auth/register", json={
        "full_name": "User Two",
        "email": "test.user2@example.com",
        "account_type": "Student",
    }).json()

    # User 1 creates a request
    client.post("/api/requests", json={
        "category_id": 1,
        "priority_id": 3,
        "room_id": 1,
        "requested_by": reg1["user_id"],
        "description": "TEST-PHASE4: Request by User One",
    })

    # User 2 creates a request
    client.post("/api/requests", json={
        "category_id": 2,
        "priority_id": 3,
        "room_id": 2,
        "requested_by": reg2["user_id"],
        "description": "TEST-PHASE4: Request by User Two",
    })

    # Check User 1's dashboard
    dash1 = client.get(f"/api/requester/{reg1['user_id']}/dashboard").json()
    assert all(r["requested_by"] == reg1["user_id"] for r in dash1["requests"])
    assert any(r["description"] == "TEST-PHASE4: Request by User One" for r in dash1["requests"])
    assert not any(r["description"] == "TEST-PHASE4: Request by User Two" for r in dash1["requests"])

    # Check User 2's dashboard
    dash2 = client.get(f"/api/requester/{reg2['user_id']}/dashboard").json()
    assert all(r["requested_by"] == reg2["user_id"] for r in dash2["requests"])
    assert any(r["description"] == "TEST-PHASE4: Request by User Two" for r in dash2["requests"])
    assert not any(r["description"] == "TEST-PHASE4: Request by User One" for r in dash2["requests"])
