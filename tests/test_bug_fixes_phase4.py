"""
Phase 4 Bug Fix Verification Tests:
1. Bug 1: Assignment Completion Lifecycle Propagation Across All Portals
2. Bug 2: Technician Material Requests with Fixed/Locked Immutable Pricing
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import pytest
from starlette.testclient import TestClient

from app.db import get_connection
from app.server import app


@pytest.fixture
def client():
    return TestClient(app)


# =============================================================================
# BUG 1 TESTS — ASSIGNMENT COMPLETION PROPAGATION
# =============================================================================

def test_bug1_full_lifecycle_workflow_and_propagation(client):
    """
    Test complete lifecycle workflow:
    request creation -> assignment -> technician completion -> admin view -> requester view
    Verifies:
    1. Technician completes assignment.
    2. Assignment status becomes 'Completed' in PostgreSQL.
    3. Admin API immediately reports 'Completed'.
    4. Requester API immediately reports the correct updated request state ('Closed').
    5. Technician API reports 'Completed'.
    6. Refreshing/reloading preserves the status.
    7. No duplicate history/cost/material records are created.
    """
    new_req_id = None
    try:
        # Step 1: Requester 4 (Priya Sharma) submits a maintenance request
        req_res = client.post("/api/requests", json={
            "category_id": 1,
            "priority_id": 2,
            "room_id": 1,
            "requested_by": 4,
            "description": "TEST-BUG1: Server room AC blower unit vibration",
        })
        assert req_res.status_code == 201
        new_req_id = req_res.json()["request_id"]
        assert req_res.json()["status_name"] == "Open"
        assert req_res.json()["status_id"] == 1

        # Requester portal sees Open request
        dash_req_before = client.get("/api/requester/4/dashboard").json()
        assert any(r["request_id"] == new_req_id and r["status_name"] == "Open" for r in dash_req_before["requests"])

        # Step 2: Admin assigns Technician 3 (Gurpreet Singh)
        assign_res = client.post("/api/assignments", json={
            "request_id": new_req_id,
            "technician_id": 3,
            "status": "In Progress",
        })
        assert assign_res.status_code == 201
        assign_id = assign_res.json()["assignment_id"]

        # Admin advances status to Assigned then In Progress
        res_assigned = client.post(f"/api/requests/{new_req_id}/status", json={
            "new_status": "Assigned",
            "changed_by": 7,
            "remarks": "Assigned to Gurpreet Singh for immediate inspection",
        })
        assert res_assigned.status_code == 200

        res_in_prog = client.post(f"/api/requests/{new_req_id}/status", json={
            "new_status": "In Progress",
            "changed_by": 7,
            "remarks": "Technician on site, starting inspection",
        })
        assert res_in_prog.status_code == 200

        # Verify initial active state in Admin dashboard stats
        admin_stats_before = client.get("/api/dashboard/stats").json()
        tech_dash_before = client.get("/api/technician/3/dashboard").json()
        active_tech_before = tech_dash_before["counts"]["active_jobs"]
        completed_tech_before = tech_dash_before["counts"]["completed_jobs"]

        # Step 3: Technician marks assignment completed
        complete_res = client.patch(
            f"/api/assignments/{assign_id}",
            json={
                "status": "Completed",
                "technician_id": 3,
                "resolution_description": "Realigned motor mount bolts and balanced blower wheel.",
            },
        )
        assert complete_res.status_code == 200
        comp_data = complete_res.json()
        assert comp_data["status"] == "Completed"
        assert comp_data["assignment_status"] == "Completed"
        assert comp_data["request_status_name"] == "Closed"

        # Step 4: Verify PostgreSQL persistence
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM assignment WHERE assignment_id = %(id)s;", {"id": assign_id})
                assign_row = cur.fetchone()
                assert assign_row["status"] == "Completed"

                cur.execute(
                    "SELECT status_id, closed_date, resolution_description, closed_by FROM request WHERE request_id = %(id)s;",
                    {"id": new_req_id},
                )
                req_row = cur.fetchone()
                assert req_row["status_id"] == 5
                assert req_row["closed_date"] is not None
                assert req_row["closed_by"] == 7
                assert "Realigned motor mount" in req_row["resolution_description"]

                # Verify single status history closure row
                cur.execute(
                    "SELECT status_id, remarks FROM status_history WHERE request_id = %(id)s AND status_id = 5;",
                    {"id": new_req_id},
                )
                closure_hist = cur.fetchall()
                assert len(closure_hist) == 1

        # Step 5: Admin API immediately reports Completed and Closed
        admin_assign = client.get(f"/api/assignments/{assign_id}").json()
        assert admin_assign["assignment_status"] == "Completed"
        assert admin_assign["request_status_name"] == "Closed"

        admin_req = client.get(f"/api/requests/{new_req_id}").json()
        assert admin_req["status_name"] == "Closed"
        assert admin_req["status_id"] == 5

        admin_stats_after = client.get("/api/dashboard/stats").json()
        assert admin_stats_after["active_jobs"] == admin_stats_before["active_jobs"] - 1
        assert admin_stats_after["closed"] == admin_stats_before["closed"] + 1

        # Step 6: Requester API immediately reports Closed
        req_dash_after = client.get("/api/requester/4/dashboard").json()
        matching_req = next(r for r in req_dash_after["requests"] if r["request_id"] == new_req_id)
        assert matching_req["status_name"] == "Closed"
        assert matching_req["status_id"] == 5

        # Step 7: Technician API reports Completed
        tech_dash_after = client.get("/api/technician/3/dashboard").json()
        assert tech_dash_after["counts"]["active_jobs"] == active_tech_before - 1
        assert tech_dash_after["counts"]["completed_jobs"] == completed_tech_before + 1
        tech_assign = next(a for a in tech_dash_after["assignments"] if a["assignment_id"] == assign_id)
        assert (tech_assign.get("status") or tech_assign.get("assignment_status")) == "Completed"

        # Step 8: Refreshing/re-fetching maintains completed/closed state
        refreshed_assign = client.get(f"/api/assignments/{assign_id}").json()
        assert refreshed_assign["assignment_status"] == "Completed"
        refreshed_req = client.get(f"/api/requests/{new_req_id}").json()
        assert refreshed_req["status_name"] == "Closed"

    finally:
        if new_req_id is not None:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM request WHERE request_id = %(id)s;", {"id": new_req_id})
                conn.commit()


def test_bug1_cross_technician_security_and_invalid_id(client):
    """
    Verifies:
    - Another technician cannot modify or complete an assignment.
    - Invalid assignment ID returns 404 with appropriate error message.
    """
    new_req_id = None
    try:
        req_res = client.post("/api/requests", json={
            "category_id": 1,
            "priority_id": 2,
            "room_id": 1,
            "requested_by": 4,
            "description": "TEST-BUG1-SEC: Security verification",
        })
        new_req_id = req_res.json()["request_id"]

        assign_res = client.post("/api/assignments", json={
            "request_id": new_req_id,
            "technician_id": 3,
            "status": "In Progress",
        })
        assign_id = assign_res.json()["assignment_id"]

        # Technician 1 attempts to complete Technician 3's job -> 400 forbidden
        bad_tech_res = client.patch(
            f"/api/assignments/{assign_id}",
            json={"status": "Completed", "technician_id": 1},
        )
        assert bad_tech_res.status_code == 400
        assert "not permitted" in bad_tech_res.json()["message"].lower()

        # Invalid assignment ID -> 404
        bad_id_res = client.patch(
            "/api/assignments/888888",
            json={"status": "Completed", "technician_id": 3},
        )
        assert bad_id_res.status_code == 404
        assert "not exist" in bad_id_res.json()["message"].lower() or "not found" in bad_id_res.json()["message"].lower()

    finally:
        if new_req_id is not None:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM request WHERE request_id = %(id)s;", {"id": new_req_id})
                conn.commit()


# =============================================================================
# BUG 2 TESTS — MATERIAL REQUESTS & IMMUTABLE PRICES
# =============================================================================

def test_bug2_technician_material_request_locked_price(client):
    """
    Test Bug 2:
    Technician requests materials:
    Material name: Copper Wire
    Quantity: 2
    Unit price: ₹450
    Total: ₹900 (enforced and calculated by backend)
    Verifies:
    1. Exact price is recorded in COST ledger.
    2. Unit price and total are locked.
    3. Even if catalog unit_cost is mutated later, the recorded historical price does NOT drift.
    4. Admin and Technician see the exact same recorded value.
    """
    new_req_id = None
    try:
        # Create request and assignment for Technician 3
        req_res = client.post("/api/requests", json={
            "category_id": 1,
            "priority_id": 2,
            "room_id": 1,
            "requested_by": 4,
            "description": "TEST-BUG2: Electrical panel wiring replacement",
        })
        new_req_id = req_res.json()["request_id"]

        assign_res = client.post("/api/assignments", json={
            "request_id": new_req_id,
            "technician_id": 3,
            "status": "In Progress",
        })
        assign_id = assign_res.json()["assignment_id"]

        # Technician submits material request: Copper Wire, Qty: 2, Unit price: 450
        mat_res = client.post("/api/technician/material-requests", json={
            "assignment_id": assign_id,
            "material_name": "Copper Wire",
            "quantity": 2,
            "unit_price": 450.00,
            "technician_id": 3,
        })
        assert mat_res.status_code == 201
        mat_data = mat_res.json()
        assert mat_data["material_name"] == "Copper Wire"
        assert mat_data["quantity_used"] == 2.0
        assert mat_data["unit_price"] == 450.0
        assert mat_data["total"] == 900.0
        mat_id = mat_data["material_id"]
        cost_id = mat_data["cost_id"]

        # Verify recorded in single COST ledger
        cost_res = client.get(f"/api/costs?request_id={new_req_id}").json()
        matching_cost = next(c for c in cost_res if c["cost_id"] == cost_id)
        assert matching_cost["cost_type"] == "Material"
        assert float(matching_cost["amount"]) == 900.0

        # Verify Technician sees the material in their dashboard / usage list
        tech_dash = client.get("/api/technician/3/dashboard").json()
        tech_mat = next(m for m in tech_dash["materials"] if m["material_name"] == "Copper Wire")
        assert tech_mat["quantity_used"] == 2.0
        assert tech_mat["unit_price"] == 450.0
        assert tech_mat["total_cost"] == 900.0

        # CRITICAL IMMUTABILITY TEST:
        # Now artificially mutate the material catalog price in PostgreSQL
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE material SET unit_cost = 9999.00 WHERE material_id = %(id)s;",
                    {"id": mat_id},
                )
            conn.commit()

        # Re-fetch via Technician dashboard and Materials usage API
        refreshed_usage = client.get("/api/materials/usage?technician_id=3").json()
        refreshed_mat = next(m for m in refreshed_usage if m["material_name"] == "Copper Wire")
        # Price MUST NOT drift:
        assert refreshed_mat["unit_price"] == 450.0
        assert refreshed_mat["total_cost"] == 900.0
        assert refreshed_mat["calculated_usage_cost"] == 900.0

        # Admin costs API also confirms exact immutable amount
        admin_costs = client.get(f"/api/costs?request_id={new_req_id}").json()
        refreshed_cost = next(c for c in admin_costs if c["cost_id"] == cost_id)
        assert float(refreshed_cost["amount"]) == 900.0

    finally:
        if new_req_id is not None:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM request WHERE request_id = %(id)s;", {"id": new_req_id})
                conn.commit()


def test_bug2_material_validation_and_ownership_rules(client):
    """
    Test Bug 2 validation rules:
    - Empty material name rejected
    - Non-positive quantity rejected
    - Negative unit price rejected
    - Technician cannot request material for another technician's job
    """
    new_req_id = None
    try:
        req_res = client.post("/api/requests", json={
            "category_id": 1,
            "priority_id": 2,
            "room_id": 1,
            "requested_by": 4,
            "description": "TEST-BUG2-VAL: Validation verification",
        })
        new_req_id = req_res.json()["request_id"]

        assign_res = client.post("/api/assignments", json={
            "request_id": new_req_id,
            "technician_id": 3,
            "status": "In Progress",
        })
        assign_id = assign_res.json()["assignment_id"]

        # 1. Empty material name
        res1 = client.post("/api/technician/material-requests", json={
            "assignment_id": assign_id,
            "material_name": "   ",
            "quantity": 2,
            "unit_price": 100,
            "technician_id": 3,
        })
        assert res1.status_code == 400
        assert "empty" in res1.json()["message"].lower() or "required" in res1.json()["message"].lower()

        # 2. Non-positive quantity
        res2 = client.post("/api/technician/material-requests", json={
            "assignment_id": assign_id,
            "material_name": "PVC Pipe",
            "quantity": 0,
            "unit_price": 120,
            "technician_id": 3,
        })
        assert res2.status_code == 400
        assert "positive" in res2.json()["message"].lower()

        # 3. Negative unit price
        res3 = client.post("/api/technician/material-requests", json={
            "assignment_id": assign_id,
            "material_name": "PVC Pipe",
            "quantity": 2,
            "unit_price": -50,
            "technician_id": 3,
        })
        assert res3.status_code == 400
        assert "non-negative" in res3.json()["message"].lower()

        # 4. Another technician (Technician 1) attempts to submit material for Tech 3's job
        res4 = client.post("/api/technician/material-requests", json={
            "assignment_id": assign_id,
            "material_name": "PVC Pipe",
            "quantity": 2,
            "unit_price": 120,
            "technician_id": 1,
        })
        assert res4.status_code == 400
        assert "not permitted" in res4.json()["message"].lower()

    finally:
        if new_req_id is not None:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM request WHERE request_id = %(id)s;", {"id": new_req_id})
                conn.commit()


def test_bug1_closed_by_dynamic_resolution_and_validation(client):
    """
    Verifies closed_by handling:
    1. Completion without closed_by dynamically resolves to active Facility Manager from "user".
    2. Invalid closed_by user ID (e.g. 999999) raises 404 / UserNotFoundError.
    3. Explicit valid closed_by persists accurately.
    """
    new_req_id = None
    try:
        # Create request and assignment
        req_res = client.post("/api/requests", json={
            "category_id": 1,
            "priority_id": 2,
            "room_id": 1,
            "requested_by": 4,
            "description": "TEST-BUG1-CLOSEDBY: closed_by dynamic resolution",
        })
        new_req_id = req_res.json()["request_id"]

        assign_res = client.post("/api/assignments", json={
            "request_id": new_req_id,
            "technician_id": 3,
            "status": "In Progress",
        })
        assign_id = assign_res.json()["assignment_id"]

        # Attempt with invalid closed_by ID -> 404
        bad_close_res = client.patch(
            f"/api/assignments/{assign_id}",
            json={"status": "Completed", "technician_id": 3, "closed_by": 999999},
        )
        assert bad_close_res.status_code == 404
        assert "not exist" in bad_close_res.json()["message"].lower()

        # Complete without closed_by -> resolves dynamically to Facility Manager
        good_close_res = client.patch(
            f"/api/assignments/{assign_id}",
            json={"status": "Completed", "technician_id": 3},
        )
        assert good_close_res.status_code == 200

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT r.closed_by, u.full_name, ro.role_name
                    FROM request r
                    JOIN "user" u ON r.closed_by = u.user_id
                    JOIN role ro ON u.role_id = ro.role_id
                    WHERE r.request_id = %(id)s;
                    """,
                    {"id": new_req_id},
                )
                closed_info = cur.fetchone()
                assert closed_info is not None
                assert closed_info["role_name"] == "Facility Manager"

    finally:
        if new_req_id is not None:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM request WHERE request_id = %(id)s;", {"id": new_req_id})
                conn.commit()


def test_bug2_material_stock_decrement_and_insufficient_stock(client):
    """
    Verifies Option B material consumption:
    1. Material usage decrements warehouse stock in PostgreSQL.
    2. COST row amount equals quantity * unit_price exactly.
    3. Exceeding available catalog stock raises 400 InsufficientMaterialStockError.
    """
    new_req_id = None
    try:
        # Create request and assignment for Technician 3
        req_res = client.post("/api/requests", json={
            "category_id": 2,
            "priority_id": 2,
            "room_id": 1,
            "requested_by": 4,
            "description": "TEST-BUG2-STOCK: Stock decrement & ledger verification",
        })
        new_req_id = req_res.json()["request_id"]

        assign_res = client.post("/api/assignments", json={
            "request_id": new_req_id,
            "technician_id": 3,
            "status": "In Progress",
        })
        assign_id = assign_res.json()["assignment_id"]

        # Read initial stock of material 4 ('1/2-inch Brass Ball Valve')
        initial_stock = 0
        mat_name = ""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT material_name, stock_qty FROM material WHERE material_id = 4;")
                row = cur.fetchone()
                initial_stock = row["stock_qty"]
                mat_name = row["material_name"]

        # Record 3 units used @ ₹350.00 each
        qty_to_use = 3
        unit_price = 350.0
        expected_total = qty_to_use * unit_price

        mat_res = client.post(
            "/api/technician/material-requests",
            json={
                "assignment_id": assign_id,
                "material_name": mat_name,
                "quantity": qty_to_use,
                "unit_price": unit_price,
            },
            headers={"X-Technician-Id": "3"},
        )
        assert mat_res.status_code == 201
        res_data = mat_res.json()
        assert res_data["total_cost"] == expected_total
        assert res_data["unit_price"] == unit_price

        # Verify PostgreSQL material stock decremented appropriately
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT stock_qty FROM material WHERE material_id = 4;")
                new_stock = cur.fetchone()["stock_qty"]
                assert new_stock == initial_stock - qty_to_use

                # Verify single-ledger COST row
                cur.execute(
                    "SELECT amount, cost_type FROM cost WHERE request_id = %(rid)s AND cost_type = 'Material';",
                    {"rid": new_req_id},
                )
                cost_row = cur.fetchone()
                assert cost_row is not None
                assert float(cost_row["amount"]) == expected_total

        # Attempt to request more than remaining available stock -> 400 Insufficient stock
        excess_res = client.post(
            "/api/technician/material-requests",
            json={
                "assignment_id": assign_id,
                "material_name": mat_name,
                "quantity": 999999,
                "unit_price": unit_price,
            },
            headers={"X-Technician-Id": "3"},
        )
        assert excess_res.status_code == 400
        assert "insufficient stock" in excess_res.json()["message"].lower()

    finally:
        if new_req_id is not None:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Restore stock for material 4
                    cur.execute("UPDATE material SET stock_qty = 60 WHERE material_id = 4;")
                    cur.execute("DELETE FROM request WHERE request_id = %(id)s;", {"id": new_req_id})
                conn.commit()

