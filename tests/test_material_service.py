"""
Unit & Integration Tests for MaterialService
Covers:
- Positive Tests (1 to 9): creation, stock deduction, cost calculation, retrievals
- Negative Tests (1 to 10): invalid inputs, stock limits, duplicates, dates, immutability
- Transaction Rollback Tests (Cases A, B, C): atomic failure and rollback verification
- Concurrency Test: row-level locking and race condition prevention
- Full Integration Chain: request -> assignment -> work_log -> material -> cost
- Strict Side-Effect Boundary: zero modifications to request state, status history, or assignments
"""

from __future__ import annotations

import concurrent.futures
from datetime import datetime
from decimal import Decimal
import pytest

from app.db import get_connection
from app.exceptions import (
    CostNotFoundError,
    DatabaseOperationError,
    DuplicateMaterialUsageError,
    InsufficientMaterialStockError,
    InvalidCostError,
    InvalidDateError,
    InvalidMaterialQuantityError,
    InvalidMaterialUsageError,
    MaterialNotFoundError,
    NotFoundError,
    TechnicianNotFoundError,
    WorkLogNotFoundError,
)
from app.repositories.base import BaseRepository
from app.repositories.cost import CostRepository
from app.repositories.material import MaterialRepository
from app.services.cost_service import CostService
from app.services.material_service import MaterialService


@pytest.fixture
def service():
    return MaterialService()


@pytest.fixture
def cost_service():
    return CostService()


# =============================================================================
# MATERIAL USAGE — POSITIVE TESTS
# =============================================================================

def test_pos_1_to_5_record_valid_material_usage_and_verify_all(service, cost_service, db_conn, isolated_work_log):
    """
    Positive 1 to 5:
    1. Record valid material usage against an existing work log
    2. Verify WORK_LOG_MATERIAL row exists with correct attributes
    3. Verify MATERIAL.stock_qty decreases correctly
    4. Verify COST row is created with CostType = 'Material'
    5. Verify COST amount equals QuantityUsed * UnitCost
    """
    # Material 1: Philips LED Tube (unit_cost=180.00, initial stock=150)
    # isolated_work_log is on Assignment 1, Request 1
    mat_before = service.get_material_by_id(1, conn=db_conn)
    initial_stock = mat_before["stock_qty"]
    unit_cost = Decimal(str(mat_before["unit_cost"]))
    qty = Decimal("3.00")
    expected_cost = (qty * unit_cost).quantize(Decimal("0.01"))  # 3 * 180 = 540.00

    usage = service.record_material_usage(
        work_log_id=isolated_work_log,
        material_id=1,
        quantity_used=qty,
        issued_by=3,  # Gurpreet Singh
        description="3 LED tubes replaced during chiller maintenance",
        conn=db_conn,
    )

    # 1. Verify result structure
    assert usage is not None
    assert usage["work_log_id"] == isolated_work_log
    assert usage["material_id"] == 1
    assert usage["quantity_used"] == qty
    assert usage["issued_by"] == 3
    assert usage["unit_cost"] == unit_cost
    assert usage["calculated_usage_cost"] == expected_cost

    # 2. Verify WORK_LOG_MATERIAL row in database
    retrieved_usage = service.get_material_usage(isolated_work_log, 1, conn=db_conn)
    assert retrieved_usage["quantity_used"] == qty
    assert retrieved_usage["material_name"] == "Philips 20W T8 LED Tube Light"
    assert retrieved_usage["issued_by_name"] == "Gurpreet Singh"

    # 3. Verify stock decreased correctly
    mat_after = service.get_material_by_id(1, conn=db_conn)
    assert mat_after["stock_qty"] == initial_stock - 3
    assert usage["remaining_stock"] == initial_stock - 3

    # 4. Verify COST row created
    cost_id = usage["cost_id"]
    cost = cost_service.get_cost_by_id(cost_id, conn=db_conn)
    assert cost["cost_type"] == "Material"
    assert cost["request_id"] == 1
    assert cost["request_number"] == "REQ-20260920-0001"
    assert cost["description"] == "3 LED tubes replaced during chiller maintenance"

    # 5. Verify COST amount equals QuantityUsed * UnitCost
    assert cost["amount"] == expected_cost


def test_pos_6_retrieve_material_usage(service, db_conn):
    """Positive 6: Retrieve material usage by composite key."""
    # Seed data has WorkLog 2 with Material 5 (R-410A gas, 2.5 kg)
    usage = service.get_material_usage(2, 5, conn=db_conn)
    assert usage is not None
    assert usage["work_log_id"] == 2
    assert usage["material_id"] == 5
    assert usage["quantity_used"] == Decimal("2.50")
    assert usage["material_name"] == "R-410A Eco Refrigerant Gas"
    assert usage["unit_cost"] == Decimal("950.00")
    assert usage["calculated_usage_cost"] == Decimal("2375.00")


def test_pos_7_list_material_usage(service, db_conn):
    """Positive 7: List material usage with filtering."""
    # List all
    all_usage = service.list_material_usage(conn=db_conn)
    assert len(all_usage) >= 4

    # Filter by work_log_id
    wl_usage = service.list_material_usage({"work_log_id": 3}, conn=db_conn)
    assert len(wl_usage) == 1
    assert wl_usage[0]["material_name"] == "Astral 1-inch CPVC Pipe (3m length)"

    # Filter by material_id
    mat_usage = service.list_material_usage({"material_id": 1}, conn=db_conn)
    assert len(mat_usage) >= 1
    assert all(u["material_id"] == 1 for u in mat_usage)


def test_pos_8_retrieve_and_list_material_costs(cost_service, db_conn):
    """Positive 8: Retrieve and list material costs from the financial ledger."""
    mat_costs = cost_service.list_costs({"cost_type": "Material"}, conn=db_conn)
    assert len(mat_costs) >= 3
    assert all(c["cost_type"] == "Material" for c in mat_costs)

    first_cost = cost_service.get_cost_by_id(mat_costs[0]["cost_id"], conn=db_conn)
    assert first_cost is not None
    assert first_cost["cost_id"] == mat_costs[0]["cost_id"]


def test_pos_9_verify_correct_request_id_in_cost(service, cost_service, db_conn):
    """Positive 9: Verify correct RequestID is derived and recorded in COST."""
    # WorkLog 5 is under Assignment 3, which is for Request 3
    wl_ctx = service.material_repo.get_work_log_context(5, conn=db_conn)
    assert wl_ctx is not None
    assert wl_ctx["request_id"] == 3
    assert wl_ctx["request_number"] == "REQ-20260922-0003"

    usage = service.record_material_usage(
        work_log_id=5,
        material_id=2,  # MCB
        quantity_used=1,
        issued_by=1,
        conn=db_conn,
    )
    cost = cost_service.get_cost_by_id(usage["cost_id"], conn=db_conn)
    assert cost["request_id"] == 3
    assert cost["request_number"] == "REQ-20260922-0003"



# =============================================================================
# MATERIAL USAGE — NEGATIVE TESTS
# =============================================================================

def test_neg_1_nonexistent_work_log(service, db_conn):
    """Negative 1: Nonexistent work log raises WorkLogNotFoundError."""
    with pytest.raises(WorkLogNotFoundError, match="Work log with ID 99999 does not exist"):
        service.record_material_usage(
            work_log_id=99999,
            material_id=1,
            quantity_used=1,
            issued_by=1,
            conn=db_conn,
        )


def test_neg_2_nonexistent_material(service, db_conn):
    """Negative 2: Nonexistent material raises MaterialNotFoundError."""
    with pytest.raises(MaterialNotFoundError, match="Material with ID 99999 does not exist"):
        service.record_material_usage(
            work_log_id=1,
            material_id=99999,
            quantity_used=1,
            issued_by=1,
            conn=db_conn,
        )


def test_neg_3_nonexistent_issued_by_technician(service, db_conn):
    """Negative 3: Nonexistent technician raises TechnicianNotFoundError."""
    with pytest.raises(TechnicianNotFoundError, match="Technician with ID 99999 does not exist"):
        service.record_material_usage(
            work_log_id=1,
            material_id=1,
            quantity_used=1,
            issued_by=99999,
            conn=db_conn,
        )


def test_neg_4_missing_required_fields(service, db_conn):
    """Negative 4: Missing required fields raise InvalidMaterialUsageError."""
    with pytest.raises(InvalidMaterialUsageError, match="Work log ID is required"):
        service.record_material_usage(
            work_log_id=None,  # type: ignore
            material_id=1,
            quantity_used=1,
            issued_by=1,
            conn=db_conn,
        )

    with pytest.raises(InvalidMaterialUsageError, match="Material ID is required"):
        service.record_material_usage(
            work_log_id=1,
            material_id=None,  # type: ignore
            quantity_used=1,
            issued_by=1,
            conn=db_conn,
        )

    with pytest.raises(InvalidMaterialUsageError, match="Quantity used is required"):
        service.record_material_usage(
            work_log_id=1,
            material_id=1,
            quantity_used=None,  # type: ignore
            issued_by=1,
            conn=db_conn,
        )

    with pytest.raises(InvalidMaterialUsageError, match="Issued-by technician ID is required"):
        service.record_material_usage(
            work_log_id=1,
            material_id=1,
            quantity_used=1,
            issued_by=None,  # type: ignore
            conn=db_conn,
        )


def test_neg_5_zero_quantity(service, db_conn):
    """Negative 5: Zero quantity raises InvalidMaterialQuantityError."""
    with pytest.raises(InvalidMaterialQuantityError, match="strictly positive"):
        service.record_material_usage(
            work_log_id=1,
            material_id=1,
            quantity_used=0,
            issued_by=1,
            conn=db_conn,
        )


def test_neg_6_negative_quantity(service, db_conn):
    """Negative 6: Negative quantity raises InvalidMaterialQuantityError."""
    with pytest.raises(InvalidMaterialQuantityError, match="strictly positive"):
        service.record_material_usage(
            work_log_id=1,
            material_id=1,
            quantity_used=-2.5,
            issued_by=1,
            conn=db_conn,
        )


def test_neg_7_quantity_greater_than_available_stock(service, db_conn):
    """Negative 7: Quantity exceeding warehouse stock raises InsufficientMaterialStockError."""
    # Material 5 has stock 30
    with pytest.raises(InsufficientMaterialStockError, match="Insufficient stock for material"):
        service.record_material_usage(
            work_log_id=1,
            material_id=5,
            quantity_used=500,
            issued_by=1,
            conn=db_conn,
        )


def test_neg_8_duplicate_work_log_material(service, db_conn):
    """Negative 8: Duplicate (WorkLogID, MaterialID) pair raises DuplicateMaterialUsageError."""
    # Seed data already contains WorkLog 2 with Material 5
    with pytest.raises(DuplicateMaterialUsageError, match="already been recorded for work log"):
        service.record_material_usage(
            work_log_id=2,
            material_id=5,
            quantity_used=1.0,
            issued_by=1,
            conn=db_conn,
        )


def test_neg_9_invalid_date(service, db_conn):
    """Negative 9: Invalid date instances raise InvalidDateError."""
    with pytest.raises(InvalidDateError, match="Issued date must be a valid datetime"):
        service.record_material_usage(
            work_log_id=1,
            material_id=1,
            quantity_used=1,
            issued_by=1,
            issued_date="invalid-date-string",  # type: ignore
            conn=db_conn,
        )

    with pytest.raises(InvalidDateError, match="Cost date must be a valid datetime"):
        service.record_material_usage(
            work_log_id=1,
            material_id=1,
            quantity_used=1,
            issued_by=1,
            cost_date="invalid-date-string",  # type: ignore
            conn=db_conn,
        )


def test_neg_10_immutable_cost_and_usage_records(service, cost_service):
    """Negative 10: Verify mutation APIs for COST and WORK_LOG_MATERIAL do not exist (read-only ledger)."""
    assert not hasattr(cost_service, "update_cost")
    assert not hasattr(cost_service, "delete_cost")
    assert not hasattr(service, "update_material_usage")
    assert not hasattr(service, "delete_material_usage")


# =============================================================================
# TRANSACTION ROLLBACK TESTS
# =============================================================================

def test_rollback_case_a_wlm_insert_fails(service, monkeypatch, db_conn):
    """
    Transaction Rollback Case A:
    When WORK_LOG_MATERIAL insertion fails, verify:
    - stock is unchanged
    - no COST row is created
    """
    mat_before = service.get_material_by_id(2, conn=db_conn)
    initial_stock = mat_before["stock_qty"]
    costs_count_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM cost", conn=db_conn)["c"]

    # Mock create_work_log_material to simulate a database failure during junction insert
    def mock_fail_wlm(*args, **kwargs):
        raise RuntimeError("Simulated failure during WORK_LOG_MATERIAL insert")

    monkeypatch.setattr(service.material_repo, "create_work_log_material", mock_fail_wlm)

    with pytest.raises(DatabaseOperationError, match="Simulated failure during WORK_LOG_MATERIAL insert"):
        service.record_material_usage(
            work_log_id=1,
            material_id=2,
            quantity_used=3,
            issued_by=1,
            conn=db_conn,
        )

    # Verify stock remained completely unchanged
    mat_after = service.get_material_by_id(2, conn=db_conn)
    assert mat_after["stock_qty"] == initial_stock

    # Verify no COST row was inserted
    costs_count_after = BaseRepository.fetch_one("SELECT count(*) AS c FROM cost", conn=db_conn)["c"]
    assert costs_count_after == costs_count_before


def test_rollback_case_b_cost_insert_fails(service, monkeypatch, db_conn):
    """
    Transaction Rollback Case B:
    When COST insertion fails, verify:
    - stock is unchanged
    - no WORK_LOG_MATERIAL row exists
    """
    mat_before = service.get_material_by_id(4, conn=db_conn)
    initial_stock = mat_before["stock_qty"]
    wlm_exists_before = service.material_repo.work_log_material_exists(1, 4, conn=db_conn)
    assert not wlm_exists_before

    # Mock create_cost to simulate a failure during ledger insert
    def mock_fail_cost(*args, **kwargs):
        raise RuntimeError("Simulated failure during COST insert")

    monkeypatch.setattr(service.cost_repo, "create_cost", mock_fail_cost)

    with pytest.raises(DatabaseOperationError, match="Simulated failure during COST insert"):
        service.record_material_usage(
            work_log_id=1,
            material_id=4,
            quantity_used=2,
            issued_by=1,
            conn=db_conn,
        )

    # Verify stock remained completely unchanged
    mat_after = service.get_material_by_id(4, conn=db_conn)
    assert mat_after["stock_qty"] == initial_stock

    # Verify no WORK_LOG_MATERIAL row was preserved
    wlm_exists_after = service.material_repo.work_log_material_exists(1, 4, conn=db_conn)
    assert not wlm_exists_after


def test_rollback_case_c_validation_failure_during_tx(service, db_conn):
    """
    Transaction Rollback Case C:
    When insufficient stock or validation fails inside the transaction:
    - no partial stock changes
    - no partial COST rows
    - no partial WORK_LOG_MATERIAL rows
    """
    mat_before = service.get_material_by_id(6, conn=db_conn)
    initial_stock = mat_before["stock_qty"]
    costs_before = BaseRepository.fetch_one("SELECT count(*) AS c FROM cost", conn=db_conn)["c"]

    with pytest.raises(InsufficientMaterialStockError):
        service.record_material_usage(
            work_log_id=1,
            material_id=6,
            quantity_used=initial_stock + 100,  # Exceeds available stock
            issued_by=1,
            conn=db_conn,
        )

    mat_after = service.get_material_by_id(6, conn=db_conn)
    assert mat_after["stock_qty"] == initial_stock

    costs_after = BaseRepository.fetch_one("SELECT count(*) AS c FROM cost", conn=db_conn)["c"]
    assert costs_after == costs_before
    assert not service.material_repo.work_log_material_exists(1, 6, conn=db_conn)


# =============================================================================
# CONCURRENCY / STOCK SAFETY TEST
# =============================================================================

def test_concurrency_stock_safety(service):
    """
    Concurrency Test:
    Demonstrates that concurrent transactions using SELECT ... FOR UPDATE row-level locking
    cannot drive stock below zero.
    
    Two concurrent threads attempt to consume 10 units each of a material with initial stock 15.
    Total requested = 20 > 15.
    Expected: Exactly one thread succeeds, the second fails with InsufficientMaterialStockError,
    and remaining stock is exactly 5 (never negative).
    """
    mat_id = 9  # Thermal Overload Relay (stock=15)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT stock_qty FROM material WHERE material_id = %s", (mat_id,))
            initial_stock = cur.fetchone()["stock_qty"]
            assert initial_stock == 15

    results = []

    def run_usage(wl_id: int, qty: int):
        try:
            res = service.record_material_usage(
                work_log_id=wl_id,
                material_id=mat_id,
                quantity_used=qty,
                issued_by=1,
                conn=None,  # Live pooled connection
            )
            return ("SUCCESS", res["remaining_stock"])
        except InsufficientMaterialStockError as err:
            return ("INSUFFICIENT_STOCK", str(err))
        except Exception as err:
            return ("ERROR", str(err))

    try:
        # Use two separate work logs so composite PK does not conflict
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(run_usage, 1, 10)
            future2 = executor.submit(run_usage, 5, 10)
            results.append(future1.result())
            results.append(future2.result())

        statuses = [r[0] for r in results]
        assert "SUCCESS" in statuses
        assert "INSUFFICIENT_STOCK" in statuses
        assert statuses.count("SUCCESS") == 1
        assert statuses.count("INSUFFICIENT_STOCK") == 1

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT stock_qty FROM material WHERE material_id = %s", (mat_id,))
                final_stock = cur.fetchone()["stock_qty"]
                assert final_stock == 5

    finally:
        # Clean up the test material usage and restore stock to preserve baseline data
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM work_log_material WHERE material_id = %s AND work_log_id IN (1, 5)", (mat_id,))
                cur.execute("DELETE FROM cost WHERE cost_type = 'Material' AND description LIKE '%Thermal Overload Relay%'")
                cur.execute("UPDATE material SET stock_qty = %s WHERE material_id = %s", (initial_stock, mat_id))
            conn.commit()


# =============================================================================
# INTEGRATION TEST (FULL CHAIN)
# =============================================================================

def test_full_chain_request_to_assignment_to_work_log_to_material_to_cost(service, cost_service, db_conn):
    """
    Integration Test:
    Verify the complete chain:
    Existing Request -> Existing Assignment -> Existing Work Log ->
    Material Usage -> Stock Deduction -> WORK_LOG_MATERIAL -> Material COST.
    Verify that the resulting COST row points to the correct REQUEST.
    """
    # Request 3: Overhead Projector repair (Assignment 3, Work Log 5)
    # Let's inspect WorkLog 5 context
    ctx = service.material_repo.get_work_log_context(5, conn=db_conn)
    assert ctx is not None
    req_id = ctx["request_id"]
    req_num = ctx["request_number"]

    # Material 7: Heavy-Duty Hydraulic Door Closer (UnitCost 1250.00, Stock 25)
    mat_before = service.get_material_by_id(7, conn=db_conn)
    stock_before = mat_before["stock_qty"]

    usage = service.record_material_usage(
        work_log_id=5,
        material_id=7,
        quantity_used=Decimal("2.00"),
        issued_by=1,  # Mahesh Chandra
        description="2 hydraulic closer units installed",
        conn=db_conn,
    )

    # Check stock deduction
    mat_after = service.get_material_by_id(7, conn=db_conn)
    assert mat_after["stock_qty"] == stock_before - 2

    # Check WORK_LOG_MATERIAL
    retrieved = service.get_material_usage(5, 7, conn=db_conn)
    assert retrieved["material_name"] == "Heavy-Duty Hydraulic Door Closer"
    assert retrieved["quantity_used"] == Decimal("2.00")
    assert retrieved["calculated_usage_cost"] == Decimal("2500.00")
    assert retrieved["request_id"] == req_id
    assert retrieved["request_number"] == req_num

    # Check COST row points to correct request
    cost = cost_service.get_cost_by_id(usage["cost_id"], conn=db_conn)
    assert cost["request_id"] == req_id
    assert cost["request_number"] == req_num
    assert cost["cost_type"] == "Material"
    assert cost["amount"] == Decimal("2500.00")


# =============================================================================
# STRICT SIDE-EFFECT BOUNDARY TEST
# =============================================================================

def test_strict_side_effect_boundary(service, db_conn):
    """
    Strict Side-Effect Boundary:
    Material usage MUST NOT automatically:
    - modify REQUEST.StatusID
    - insert STATUS_HISTORY
    - close the request
    - create FEEDBACK
    - create another ASSIGNMENT
    - modify WORK_LOG
    - modify technician records
    """
    # WorkLog 1 is under Assignment 1, Request 1
    req_before = BaseRepository.fetch_one("SELECT * FROM request WHERE request_id = 1", conn=db_conn)
    sh_count_before = BaseRepository.fetch_one(
        "SELECT count(*) AS c FROM status_history WHERE request_id = 1", conn=db_conn
    )["c"]
    assign_count_before = BaseRepository.fetch_one(
        "SELECT count(*) AS c FROM assignment WHERE request_id = 1", conn=db_conn
    )["c"]
    fb_count_before = BaseRepository.fetch_one(
        "SELECT count(*) AS c FROM feedback WHERE request_id = 1", conn=db_conn
    )["c"]
    wl_before = BaseRepository.fetch_one("SELECT * FROM work_log WHERE work_log_id = 1", conn=db_conn)
    tech_before = BaseRepository.fetch_one("SELECT * FROM technician WHERE technician_id = 3", conn=db_conn)

    # Record material usage
    service.record_material_usage(
        work_log_id=1,
        material_id=8,  # Washbasin Spindle
        quantity_used=Decimal("1.00"),
        issued_by=3,
        conn=db_conn,
    )

    # Verify REQUEST state is untouched
    req_after = BaseRepository.fetch_one("SELECT * FROM request WHERE request_id = 1", conn=db_conn)
    assert req_after["status_id"] == req_before["status_id"]
    assert req_after["closed_date"] == req_before["closed_date"]
    assert req_after["resolution_description"] == req_before["resolution_description"]
    assert req_after["closed_by"] == req_before["closed_by"]

    # Verify STATUS_HISTORY count is untouched
    sh_count_after = BaseRepository.fetch_one(
        "SELECT count(*) AS c FROM status_history WHERE request_id = 1", conn=db_conn
    )["c"]
    assert sh_count_after == sh_count_before

    # Verify ASSIGNMENT count is untouched
    assign_count_after = BaseRepository.fetch_one(
        "SELECT count(*) AS c FROM assignment WHERE request_id = 1", conn=db_conn
    )["c"]
    assert assign_count_after == assign_count_before

    # Verify FEEDBACK count is untouched
    fb_count_after = BaseRepository.fetch_one(
        "SELECT count(*) AS c FROM feedback WHERE request_id = 1", conn=db_conn
    )["c"]
    assert fb_count_after == fb_count_before

    # Verify WORK_LOG is untouched
    wl_after = BaseRepository.fetch_one("SELECT * FROM work_log WHERE work_log_id = 1", conn=db_conn)
    assert wl_after["hours_spent"] == wl_before["hours_spent"]
    assert wl_after["work_description"] == wl_before["work_description"]
    assert wl_after["work_date"] == wl_before["work_date"]

    # Verify TECHNICIAN is untouched
    tech_after = BaseRepository.fetch_one("SELECT * FROM technician WHERE technician_id = 3", conn=db_conn)
    assert tech_after["labor_rate"] == tech_before["labor_rate"]
    assert tech_after["status"] == tech_before["status"]
