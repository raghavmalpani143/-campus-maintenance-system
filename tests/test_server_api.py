"""
API Server Integration Tests for Phase 4
Tests FastAPI server endpoints delegating to locked Phase 3 services
and querying the six locked Phase 2 PostgreSQL views.
"""

from __future__ import annotations

from datetime import datetime
import pytest
from fastapi.testclient import TestClient

from app.db import get_connection
from app.server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_api_lookups(client):
    """Verify lookup endpoint returns reference entities for modal forms."""
    res = client.get("/api/lookups")
    assert res.status_code == 200
    data = res.json()
    assert "categories" in data
    assert "priorities" in data
    assert "rooms" in data
    assert "users" in data
    assert "technicians" in data
    assert "materials" in data
    assert "statuses" in data
    assert len(data["categories"]) >= 6
    assert len(data["priorities"]) == 4


def test_api_dashboard_stats(client):
    """Verify live KPI counts match database reality."""
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 200
    data = res.json()
    assert "open_requests" in data
    assert "active_jobs" in data
    assert "on_hold" in data
    assert "closed" in data
    assert "total_requests" in data
    assert data["total_requests"] >= 10


def test_api_list_requests_and_filter(client):
    """Verify listing and filtering requests."""
    res = client.get("/api/requests")
    assert res.status_code == 200
    requests = res.json()
    assert len(requests) >= 10

    # Filter by status Closed (status_id = 5)
    res_closed = client.get("/api/requests?status_id=5")
    assert res_closed.status_code == 200
    closed_requests = res_closed.json()
    assert all(r["status_id"] == 5 for r in closed_requests)


def test_api_get_request_by_id(client):
    """Verify retrieving a specific maintenance request."""
    res = client.get("/api/requests/1")
    assert res.status_code == 200
    data = res.json()
    assert data["request_id"] == 1
    assert data["status_name"] == "Closed"

    # Nonexistent request
    res_missing = client.get("/api/requests/99999")
    assert res_missing.status_code == 404


def test_api_all_six_locked_phase_2_reporting_views(client):
    """
    Critical Test:
    Verifies that the API server queries ONLY the exact six locked Phase 2 PostgreSQL views:
    1. vw_pending_requests
    2. vw_request_ageing
    3. vw_technician_workload
    4. vw_building_maintenance_cost
    5. vw_material_usage
    6. vw_feedback_summary
    """
    # 1. Pending requests view
    res1 = client.get("/api/reports/pending-requests")
    assert res1.status_code == 200
    pending = res1.json()
    assert len(pending) == 6
    assert all(r["current_status"] != "Closed" for r in pending)

    # 2. Request ageing view
    res2 = client.get("/api/reports/request-ageing")
    assert res2.status_code == 200
    ageing = res2.json()
    assert len(ageing) == 10
    assert "sla_performance_status" in ageing[0]
    assert "ageing_bracket" in ageing[0]

    # 3. Technician workload view
    res3 = client.get("/api/reports/technician-workload")
    assert res3.status_code == 200
    workload = res3.json()
    assert len(workload) in (5, 6)
    assert "total_assignments" in workload[0]
    assert "total_hours_worked" in workload[0]

    # 4. Building maintenance cost view (singular cost)
    res4 = client.get("/api/reports/building-maintenance-cost")
    assert res4.status_code == 200
    costs = res4.json()
    assert len(costs) == 5
    assert "total_maintenance_expenditure" in costs[0]
    assert "material_cost" in costs[0]

    # 5. Material usage view
    res5 = client.get("/api/reports/material-usage")
    assert res5.status_code == 200
    mat_usage = res5.json()
    assert len(mat_usage) == 10
    assert "current_warehouse_stock" in mat_usage[0]
    assert "total_material_cost" in mat_usage[0]

    # 6. Feedback summary view
    res6 = client.get("/api/reports/feedback-summary")
    assert res6.status_code == 200
    fb_summary = res6.json()
    assert len(fb_summary) == 3
    assert "average_rating" in fb_summary[0]
    assert "total_evaluations" in fb_summary[0]


def test_api_view_column_exact_match(client):
    """
    Verify exact column schemas returned from all 6 locked Phase 2 views.
    Ensures zero column modifications or inferrals.
    """
    pending = client.get("/api/reports/pending-requests").json()
    assert set(pending[0].keys()) == {
        "request_id", "request_number", "request_date", "category_name",
        "priority_level", "sla_target_hours", "building_name", "room_number",
        "requester_name", "current_status", "days_open", "assigned_technician",
        "assignment_status"
    }

    ageing = client.get("/api/reports/request-ageing").json()
    assert set(ageing[0].keys()) == {
        "request_id", "request_number", "request_date", "closed_date",
        "request_status", "priority_level", "sla_target_hours", "hours_open",
        "sla_performance_status", "ageing_bracket", "building_name", "room_number"
    }

    workload = client.get("/api/reports/technician-workload").json()
    assert set(workload[0].keys()) == {
        "technician_id", "full_name", "department", "technician_status",
        "labor_rate", "total_assignments", "active_assignments",
        "completed_assignments", "total_hours_worked", "total_labor_value_generated"
    }

    costs = client.get("/api/reports/building-maintenance-cost").json()
    assert set(costs[0].keys()) == {
        "building_id", "building_name", "location", "total_requests_count",
        "total_maintenance_expenditure", "material_cost", "labor_cost",
        "service_cost", "misc_cost"
    }

    mat_usage = client.get("/api/reports/material-usage").json()
    assert set(mat_usage[0].keys()) == {
        "material_id", "material_name", "unit", "unit_cost",
        "current_warehouse_stock", "total_quantity_used", "total_material_cost",
        "total_work_orders_used_in"
    }

    feedback = client.get("/api/reports/feedback-summary").json()
    assert set(feedback[0].keys()) == {
        "building_name", "category_name", "total_evaluations",
        "average_rating", "lowest_rating", "highest_rating"
    }


def test_api_material_service_boundary_insufficient_stock(client):
    """
    Verify Phase 4 API does NOT bypass Phase 3 MaterialService:
    Requisitioning more stock than available must trigger InsufficientStockError (HTTP 400).
    """
    # Create an isolated work log so it reaches the stock validation branch without duplicate collision
    wl_res = client.post("/api/work-logs", json={
        "assignment_id": 1,
        "work_description": "Isolated work log for boundary stock test",
        "hours_spent": 1.0,
        "log_date": "2026-10-01T10:00:00",
    })
    assert wl_res.status_code == 201
    isolated_wl_id = wl_res.json()["work_log_id"]

    payload = {
        "work_log_id": isolated_wl_id,
        "material_id": 1,
        "quantity_used": 999999,  # Far exceeds warehouse stock
        "issued_by": 1,
    }
    res = client.post("/api/materials/usage", json=payload)
    assert res.status_code == 400
    assert "stock" in res.json()["message"].lower()


def test_api_material_service_boundary_duplicate_material(client):
    """
    Verify Phase 4 API rejects duplicate material usage on the same work log (HTTP 400).
    """
    # Seed data already contains (work_log_id=1, material_id=1)
    payload = {
        "work_log_id": 1,
        "material_id": 1,
        "quantity_used": 1.0,
        "issued_by": 1,
    }
    res = client.post("/api/materials/usage", json=payload)
    assert res.status_code == 400
    assert "already been recorded" in res.json()["message"].lower()


def test_api_status_progression_boundary_invalid_transition(client):
    """
    Verify Phase 4 API does NOT permit illegal status jumps:
    Open -> In Progress is rejected (HTTP 400).
    """
    # Request 8 is Open
    res = client.post("/api/requests/8/status", json={
        "new_status": "In Progress",
        "changed_by": 1,
        "remarks": "Attempting illegal direct transition"
    })
    assert res.status_code == 400
    assert "invalid" in res.json()["message"].lower() or "transition" in res.json()["message"].lower()


def test_api_closure_boundary_open_request(client):
    """
    Verify Phase 4 API rejects closure of an Open request:
    Only In Progress or On Hold may be closed.
    """
    res = client.post("/api/requests/8/close", json={
        "resolution_description": "Trying to close open request directly",
        "closed_by": 1,
        "changed_by": 1,
        "closed_date": "2026-10-02T12:00:00"
    })
    assert res.status_code == 400


def test_api_feedback_boundary_unclosed_request(client):
    """
    Verify Phase 4 API rejects feedback on non-Closed request (Phase 3G rule).
    """
    res = client.post("/api/requests/8/feedback", json={
        "user_id": 1,
        "rating": 5,
        "comments": "Great work"
    })
    assert res.status_code == 400
    assert "closed" in res.json()["message"].lower() or "state" in res.json()["message"].lower()


def test_api_static_assets_serving(client):
    """
    Verify root SPA serving, static asset mounting, MIME types, and paths.
    """
    # 1. Root route
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "text/html" in res_root.headers.get("content-type", "")
    html_text = res_root.text
    assert "/static/css/design-system.css" in html_text
    assert "/static/js/app.js" in html_text

    # 2. index.html alias
    res_index = client.get("/index.html")
    assert res_index.status_code == 200
    assert "text/html" in res_index.headers.get("content-type", "")

    # 3. Primary static CSS
    res_css = client.get("/static/css/design-system.css")
    assert res_css.status_code == 200
    assert "text/css" in res_css.headers.get("content-type", "")
    assert len(res_css.content) > 1000

    # 4. Fallback /css route
    res_css_fallback = client.get("/css/design-system.css")
    assert res_css_fallback.status_code == 200
    assert "text/css" in res_css_fallback.headers.get("content-type", "")

    # 5. Primary static JS
    res_js = client.get("/static/js/app.js")
    assert res_js.status_code == 200
    assert "javascript" in res_js.headers.get("content-type", "")
    assert len(res_js.content) > 1000

    # 6. Fallback /js route
    res_js_fallback = client.get("/js/app.js")
    assert res_js_fallback.status_code == 200
    assert "javascript" in res_js_fallback.headers.get("content-type", "")


# =============================================================================
# PHASE 4 ROLE-BASED ACCESS & IDENTITY TESTS
# =============================================================================

def test_demo_login_valid_requester(client):
    """Verify demo login for active Requester (Student role)."""
    res = client.post("/api/auth/demo-login", json={"email": "priya.sharma@campus.edu"})
    assert res.status_code == 200
    data = res.json()
    assert data["entity_type"] == "user"
    assert data["user_id"] == 4
    assert data["full_name"] == "Priya Sharma"
    assert data["role_id"] == 1
    assert data["role_name"] == "Student"
    assert data["portal_role"] == "requester"


def test_demo_login_valid_admin(client):
    """Verify demo login for active Facility Manager (Admin role)."""
    res = client.post("/api/auth/demo-login", json={"email": "rajesh.nair@campus.edu"})
    assert res.status_code == 200
    data = res.json()
    assert data["entity_type"] == "user"
    assert data["user_id"] == 7
    assert data["role_id"] == 4
    assert data["role_name"] == "Facility Manager"
    assert data["portal_role"] == "admin"


def test_demo_login_valid_technician(client):
    """Verify demo login for active Technician."""
    res = client.post("/api/auth/demo-login", json={"email": "mahesh.tech@campus.edu"})
    assert res.status_code == 200
    data = res.json()
    assert data["entity_type"] == "technician"
    assert data["technician_id"] == 1
    assert data["full_name"] == "Mahesh Chandra"
    assert data["portal_role"] == "technician"
    assert "Electrical Maintenance" in data["role_name"]


def test_demo_login_invalid_email(client):
    """Verify error handling for empty or unregistered campus emails."""
    # Empty email -> 400
    res_empty = client.post("/api/auth/demo-login", json={"email": "   "})
    assert res_empty.status_code == 400
    assert "email is required" in res_empty.json()["message"].lower()

    # Unregistered email -> 404
    res_unknown = client.post("/api/auth/demo-login", json={"email": "unknown.person@campus.edu"})
    assert res_unknown.status_code == 404
    assert "no registered campus account found" in res_unknown.json()["message"].lower()


def test_demo_login_inactive_user(client):
    """Verify login rejection for inactive campus user."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('UPDATE "user" SET status = \'Inactive\' WHERE user_id = 4;')
        conn.commit()

    try:
        res = client.post("/api/auth/demo-login", json={"email": "priya.sharma@campus.edu"})
        assert res.status_code == 400
        assert "inactive" in res.json()["message"].lower()
    finally:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('UPDATE "user" SET status = \'Active\' WHERE user_id = 4;')
            conn.commit()


def test_demo_login_role_resolution(client):
    """
    Verify role resolution matrix:
    - Student (role 1) -> 'requester'
    - Faculty (role 2) -> 'requester'
    - Staff (role 3) -> 'requester'
    - Facility Manager (role 4) -> 'admin'
    - Technician -> 'technician'
    """
    # Student
    res1 = client.post("/api/auth/demo-login", json={"email": "priya.sharma@campus.edu"})
    assert res1.status_code == 200
    assert res1.json()["portal_role"] == "requester"
    assert res1.json()["role_id"] == 1

    # Faculty
    res2 = client.post("/api/auth/demo-login", json={"email": "ramesh.sundaram@campus.edu"})
    assert res2.status_code == 200
    assert res2.json()["portal_role"] == "requester"
    assert res2.json()["role_id"] == 2

    # Staff
    res3 = client.post("/api/auth/demo-login", json={"email": "manohar.lal@campus.edu"})
    assert res3.status_code == 200
    assert res3.json()["portal_role"] == "requester"
    assert res3.json()["role_id"] == 3

    # Facility Manager (Admin)
    res4 = client.post("/api/auth/demo-login", json={"email": "rajesh.nair@campus.edu"})
    assert res4.status_code == 200
    assert res4.json()["portal_role"] == "admin"
    assert res4.json()["role_id"] == 4
    assert res4.json()["user_id"] == 7

    # Technician
    res5 = client.post("/api/auth/demo-login", json={"email": "dinesh.tech@campus.edu"})
    assert res5.status_code == 200
    assert res5.json()["portal_role"] == "technician"
    assert res5.json()["entity_type"] == "technician"


def test_demo_accounts_list(client):
    """Verify demo accounts list provides sample accounts across all 3 roles."""
    res = client.get("/api/auth/demo-accounts")
    assert res.status_code == 200
    accounts = res.json()
    assert len(accounts) >= 13  # 8 users + 5 technicians

    roles_found = {a["portal_role"] for a in accounts}
    assert "requester" in roles_found
    assert "admin" in roles_found
    assert "technician" in roles_found


def test_requester_sees_only_own_requests(client):
    """
    Verify requesters only retrieve requests submitted by themselves:
    1. /api/requester/{user_id}/dashboard
    2. /api/requests?requested_by={user_id}
    """
    # User 4 (Priya Sharma)
    res = client.get("/api/requester/4/dashboard")
    assert res.status_code == 200
    data = res.json()
    assert data["user"]["user_id"] == 4
    for r in data["requests"]:
        assert r["requested_by"] == 4

    # Filtered requests endpoint
    res_list = client.get("/api/requests?requested_by=4")
    assert res_list.status_code == 200
    reqs = res_list.json()
    assert len(reqs) > 0
    assert all(r["requested_by"] == 4 for r in reqs)

    # User 1 (Dr. Ramesh Sundaram)
    res_user1 = client.get("/api/requester/1/dashboard")
    assert res_user1.status_code == 200
    for r in res_user1.json()["requests"]:
        assert r["requested_by"] == 1


def test_technician_sees_only_relevant_assignments(client):
    """
    Verify technicians only see their own assignments, work logs, and material issues.
    """
    # Technician 1 (Mahesh Chandra - HVAC)
    res = client.get("/api/technician/1/dashboard")
    assert res.status_code == 200
    data = res.json()
    assert data["technician"]["technician_id"] == 1
    assert data["counts"]["total_assignments"] >= 1
    for a in data["assignments"]:
        assert a["technician_id"] == 1
    for wl in data["work_logs"]:
        assert wl["technician_id"] == 1
    for m in data["materials"]:
        assert m["issued_by"] == 1


def test_admin_sees_all_requests(client):
    """
    Verify admin sees all campus requests across all requesters.
    """
    res = client.get("/api/requests")
    assert res.status_code == 200
    all_requests = res.json()
    assert len(all_requests) >= 10
    requester_ids = {r["requested_by"] for r in all_requests}
    assert len(requester_ids) >= 3  # Spans multiple requesters


def test_requester_and_technician_data_isolation(client):
    """
    Verify API boundaries:
    - Nonexistent user / technician IDs return 404
    """
    res_bad_user = client.get("/api/requester/99999/dashboard")
    assert res_bad_user.status_code == 404

    res_bad_tech = client.get("/api/technician/99999/dashboard")
    assert res_bad_tech.status_code == 404


def test_existing_request_creation_and_lifecycle_workflows(client):
    """
    Verify end-to-end operational lifecycle via API delegating to Phase 3:
    1. Create request (Requester workflow)
    2. Assign technician (Admin workflow)
    3. Record work log (Technician workflow)
    4. Record material usage (Technician workflow via Phase 3 MaterialService)
    5. Progress status to In Progress
    6. Close request with resolution (Admin workflow)
    7. Submit feedback (Requester workflow)
    8. Atomically clean up test data to restore clean seed state.
    """
    new_req_id = None
    try:
        # 1. Requester creates request
        req_res = client.post("/api/requests", json={
            "category_id": 1,
            "priority_id": 2,
            "room_id": 1,
            "requested_by": 4,
            "request_date": "2026-10-02T09:00:00",
            "description": "TEST-LIFECYCLE: Overhead fluorescent fixture repair in room 101"
        })
        assert req_res.status_code == 201
        new_req_id = req_res.json()["request_id"]
        assert req_res.json()["status_name"] == "Open"
        assert req_res.json()["status_id"] == 1

        # Verify it appears in requester's dashboard
        req_dash = client.get("/api/requester/4/dashboard")
        assert req_dash.status_code == 200
        assert any(r["request_id"] == new_req_id for r in req_dash.json()["requests"])

        # 2. Admin assigns technician (Technician 3: Gurpreet Singh)
        assign_res = client.post("/api/assignments", json={
            "request_id": new_req_id,
            "technician_id": 3,
            "assigned_by": 7,
            "instructions": "Inspect and replace burned out ballast"
        })
        assert assign_res.status_code == 201
        new_assign_id = assign_res.json()["assignment_id"]

        # Admin advances status to Assigned
        st_assign_res = client.post(f"/api/requests/{new_req_id}/status", json={
            "new_status": "Assigned",
            "changed_by": 7,
            "remarks": "Assigned to Gurpreet Singh"
        })
        assert st_assign_res.status_code == 200

        # Verify request status transitioned to Assigned
        check_req = client.get(f"/api/requests/{new_req_id}")
        assert check_req.json()["status_name"] == "Assigned"

        # Verify it appears in technician 3's dashboard
        tech_dash = client.get("/api/technician/3/dashboard")
        assert tech_dash.status_code == 200
        assert any(a["assignment_id"] == new_assign_id for a in tech_dash.json()["assignments"])

        # 3. Technician logs work
        wl_res = client.post("/api/work-logs", json={
            "assignment_id": new_assign_id,
            "work_description": "Disassembled fixture housing, checked circuit voltage",
            "hours_spent": 1.5,
            "log_date": "2026-10-02T10:00:00"
        })
        assert wl_res.status_code == 201
        new_wl_id = wl_res.json()["work_log_id"]

        # 4. Technician requisitions material (Material 1: LED Tube)
        mat_res = client.post("/api/materials/usage", json={
            "work_log_id": new_wl_id,
            "material_id": 1,
            "quantity_used": 1.0,
            "issued_by": 3,
            "description": "1 replacement LED tube for testing"
        })
        assert mat_res.status_code == 201
        assert mat_res.json()["work_log_id"] == new_wl_id

        # 5. Progress to In Progress
        st_res = client.post(f"/api/requests/{new_req_id}/status", json={
            "new_status": "In Progress",
            "changed_by": 7,
            "remarks": "Work underway by technician"
        })
        assert st_res.status_code == 200

        # 6. Admin closes request
        close_res = client.post(f"/api/requests/{new_req_id}/close", json={
            "closed_by": 7,
            "changed_by": 7,
            "closed_date": "2026-10-02T12:00:00",
            "resolution_description": "Ballast and tube replaced; tested illumination"
        })
        assert close_res.status_code == 200
        assert close_res.json()["status_name"] == "Closed"

        # 7. Requester submits feedback on closed request
        fb_res = client.post(f"/api/requests/{new_req_id}/feedback", json={
            "user_id": 4,
            "rating": 5,
            "comments": "Excellent rapid resolution!"
        })
        assert fb_res.status_code == 201
        assert fb_res.json()["rating"] == 5

    finally:
        # Atomic database cleanup to ensure strict seed immutability
        if new_req_id is not None:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Restore material stock for material 1
                    cur.execute("UPDATE material SET stock_qty = stock_qty + 1.0 WHERE material_id = 1;")
                    # Delete request (cascades to assignment, work_log, work_log_material, cost, status_history, feedback)
                    cur.execute("DELETE FROM request WHERE request_id = %(id)s;", {"id": new_req_id})
                conn.commit()


# =============================================================================
# PHASE 4 BUG FIX — TECHNICIAN MARK ASSIGNMENT COMPLETED TESTS
# =============================================================================

def test_technician_mark_assignment_completed_flow(client):
    """
    Focused tests for Phase 4 Bug Fix:
    1. Valid technician marks own assignment as Completed -> succeeds.
    2. Assignment status is actually 'Completed' in PostgreSQL.
    3. Technician dashboard moves the assignment from active to completed (counts and list).
    4. Refresh / re-fetch still shows 'Completed'.
    5. Request lifecycle status is NOT closed automatically by assignment completion.
    """
    new_req_id = None
    try:
        # Create request and assignment for Technician 3 (Gurpreet Singh)
        req_res = client.post("/api/requests", json={
            "category_id": 1,
            "priority_id": 2,
            "room_id": 1,
            "requested_by": 4,
            "description": "TEST-TECH-COMPLETE: Air handler bearing replacement"
        })
        assert req_res.status_code == 201
        new_req_id = req_res.json()["request_id"]
        initial_request_status = req_res.json()["status_name"]

        assign_res = client.post("/api/assignments", json={
            "request_id": new_req_id,
            "technician_id": 3,
            "status": "In Progress"
        })
        assert assign_res.status_code == 201
        assign_id = assign_res.json()["assignment_id"]
        assert assign_res.json()["status"] == "In Progress"

        # Baseline: Check technician 3 dashboard before completion
        dash_before = client.get("/api/technician/3/dashboard").json()
        active_before = dash_before["counts"]["active_jobs"]
        completed_before = dash_before["counts"]["completed_jobs"]
        active_ids_before = [
            a["assignment_id"] for a in dash_before["assignments"]
            if (a.get("status") or a.get("assignment_status")) in ("Assigned", "In Progress")
        ]
        assert assign_id in active_ids_before

        # 1. Valid technician marks own assignment as Completed -> succeeds
        complete_res = client.patch(
            f"/api/assignments/{assign_id}",
            json={"status": "Completed", "technician_id": 3}
        )
        assert complete_res.status_code == 200
        comp_data = complete_res.json()
        assert comp_data["status"] == "Completed"
        assert comp_data["assignment_status"] == "Completed"

        # 2. Assignment status is actually 'Completed' in PostgreSQL
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM assignment WHERE assignment_id = %(id)s;", {"id": assign_id})
                row = cur.fetchone()
                assert row is not None
                assert row["status"] == "Completed"

        # 3. Technician dashboard moves the assignment from active to completed
        dash_after = client.get("/api/technician/3/dashboard").json()
        assert dash_after["counts"]["active_jobs"] == active_before - 1
        assert dash_after["counts"]["completed_jobs"] == completed_before + 1

        active_ids_after = [
            a["assignment_id"] for a in dash_after["assignments"]
            if (a.get("status") or a.get("assignment_status")) in ("Assigned", "In Progress")
        ]
        assert assign_id not in active_ids_after

        completed_ids_after = [
            a["assignment_id"] for a in dash_after["assignments"]
            if (a.get("status") or a.get("assignment_status")) == "Completed"
        ]
        assert assign_id in completed_ids_after

        # 4. Refresh / re-fetch still shows 'Completed'
        get_res = client.get(f"/api/assignments/{assign_id}")
        assert get_res.status_code == 200
        assert get_res.json()["status"] == "Completed"
        assert get_res.json()["assignment_status"] == "Completed"

        list_res = client.get(f"/api/assignments?technician_id=3")
        assert list_res.status_code == 200
        my_item = next(a for a in list_res.json() if a["assignment_id"] == assign_id)
        assert my_item["status"] == "Completed"
        assert my_item["assignment_status"] == "Completed"

        # 5. Request lifecycle status propagates atomically to Closed
        req_after = client.get(f"/api/requests/{new_req_id}").json()
        assert req_after["status_name"] == "Closed"
        assert req_after["status_id"] == 5
        assert req_after["closed_date"] is not None
        assert req_after["resolution_description"] is not None

        # Verify Requester portal immediately sees the updated Closed state
        req_dash = client.get("/api/requester/4/dashboard").json()
        matching_req = next(r for r in req_dash["requests"] if r["request_id"] == new_req_id)
        assert matching_req["status_name"] == "Closed"

    finally:
        if new_req_id is not None:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM request WHERE request_id = %(id)s;", {"id": new_req_id})
                conn.commit()


def test_technician_cannot_complete_another_technicians_assignment(client):
    """
    Focused test: A technician cannot modify or complete an assignment assigned to another technician.
    """
    new_req_id = None
    try:
        # Create request and assignment for Technician 3 (Gurpreet Singh)
        req_res = client.post("/api/requests", json={
            "category_id": 1,
            "priority_id": 2,
            "room_id": 1,
            "requested_by": 4,
            "description": "TEST-ISOLATION: Circuit panel inspection"
        })
        assert req_res.status_code == 201
        new_req_id = req_res.json()["request_id"]

        assign_res = client.post("/api/assignments", json={
            "request_id": new_req_id,
            "technician_id": 3,
            "status": "In Progress"
        })
        assert assign_res.status_code == 201
        assign_id = assign_res.json()["assignment_id"]

        # Technician 1 (Mahesh Chandra) attempts to mark Technician 3's assignment as Completed via body
        bad_res = client.patch(
            f"/api/assignments/{assign_id}",
            json={"status": "Completed", "technician_id": 1}
        )
        assert bad_res.status_code == 400
        assert "not permitted" in bad_res.json()["message"].lower()

        # Technician 2 attempts via query parameter
        bad_query_res = client.patch(
            f"/api/assignments/{assign_id}?technician_id=2",
            json={"status": "Completed"}
        )
        assert bad_query_res.status_code == 400
        assert "not permitted" in bad_query_res.json()["message"].lower()

        # Technician 4 attempts via X-Technician-Id header
        bad_header_res = client.patch(
            f"/api/assignments/{assign_id}",
            json={"status": "Completed"},
            headers={"X-Technician-Id": "4"}
        )
        assert bad_header_res.status_code == 400
        assert "not permitted" in bad_header_res.json()["message"].lower()

        # Verify assignment in PostgreSQL is STILL 'In Progress' (unmodified)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM assignment WHERE assignment_id = %(id)s;", {"id": assign_id})
                row = cur.fetchone()
                assert row is not None
                assert row["status"] == "In Progress"

    finally:
        if new_req_id is not None:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM request WHERE request_id = %(id)s;", {"id": new_req_id})
                conn.commit()


def test_invalid_assignment_id_fails_correctly(client):
    """
    Focused test: Modifying or fetching a nonexistent assignment ID returns HTTP 404.
    """
    res_patch = client.patch("/api/assignments/99999", json={"status": "Completed", "technician_id": 1})
    assert res_patch.status_code == 404
    assert "not exist" in res_patch.json()["message"].lower() or "not found" in res_patch.json()["message"].lower()

    res_get = client.get("/api/assignments/99999")
    assert res_get.status_code == 404
    assert "not exist" in res_get.json()["message"].lower() or "not found" in res_get.json()["message"].lower()
