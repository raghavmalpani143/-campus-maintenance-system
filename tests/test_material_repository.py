"""
Unit & Integration Tests for MaterialRepository
Verifies parameterized SQL execution, row-level locking, stock decrements,
and relational joins for WORK_LOG_MATERIAL.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import pytest

from app.repositories.material import MaterialRepository


@pytest.fixture
def repo():
    return MaterialRepository()


def test_repo_get_material_by_id(repo, db_conn):
    """Test retrieving material item by primary key."""
    mat = repo.get_material_by_id(1, conn=db_conn)
    assert mat is not None
    assert mat["material_id"] == 1
    assert mat["material_name"] == "Philips 20W T8 LED Tube Light"
    assert mat["unit"] == "Piece"
    assert mat["unit_cost"] == Decimal("180.00")
    assert mat["stock_qty"] >= 0

    assert repo.get_material_by_id(99999, conn=db_conn) is None


def test_repo_get_material_for_update(repo, db_conn):
    """Test locking material row using SELECT ... FOR UPDATE."""
    mat = repo.get_material_for_update(2, conn=db_conn)
    assert mat is not None
    assert mat["material_id"] == 2
    assert mat["material_name"] == "Havells 16A Single Pole MCB"


def test_repo_decrement_stock(repo, db_conn):
    """Test atomic stock decrement within transaction."""
    mat_before = repo.get_material_by_id(3, conn=db_conn)
    assert mat_before is not None
    initial_stock = mat_before["stock_qty"]

    updated = repo.decrement_stock(3, Decimal("5"), conn=db_conn)
    assert updated is not None
    assert updated["stock_qty"] == initial_stock - 5

    mat_after = repo.get_material_by_id(3, conn=db_conn)
    assert mat_after is not None
    assert mat_after["stock_qty"] == initial_stock - 5


def test_repo_create_and_get_material_usage(repo, db_conn, isolated_work_log):
    """Test inserting and retrieving material usage record with rich joined context."""
    now = datetime(2026, 10, 1, 11, 0, 0)
    created = repo.create_work_log_material(
        {
            "work_log_id": isolated_work_log,
            "material_id": 1,
            "quantity_used": Decimal("4.00"),
            "issued_date": now,
            "issued_by": 3,  # Gurpreet Singh
        },
        conn=db_conn,
    )
    assert created["work_log_id"] == isolated_work_log
    assert created["material_id"] == 1
    assert created["quantity_used"] == Decimal("4.00")
    assert created["issued_by"] == 3

    usage = repo.get_material_usage(isolated_work_log, 1, conn=db_conn)
    assert usage is not None
    assert usage["work_log_id"] == isolated_work_log
    assert usage["material_id"] == 1
    assert usage["material_name"] == "Philips 20W T8 LED Tube Light"
    assert usage["material_unit"] == "Piece"
    assert usage["unit_cost"] == Decimal("180.00")
    assert usage["calculated_usage_cost"] == Decimal("720.00")
    assert usage["issued_by_name"] == "Gurpreet Singh"
    assert usage["assignment_id"] == 1
    assert usage["request_id"] == 1
    assert usage["request_number"] == "REQ-20260920-0001"


def test_repo_duplicate_material_raises_unique_violation(repo, db_conn):
    """Test that attempting to insert duplicate (work_log_id, material_id) raises UniqueViolation."""
    import psycopg.errors
    # Seed data already contains (work_log_id=1, material_id=1)
    with pytest.raises(psycopg.errors.UniqueViolation):
        repo.create_work_log_material(
            {
                "work_log_id": 1,
                "material_id": 1,
                "quantity_used": Decimal("2.00"),
                "issued_date": datetime(2026, 10, 1, 12, 0, 0),
                "issued_by": 1,
            },
            conn=db_conn,
        )


def test_repo_work_log_material_exists(repo, db_conn):
    """Test checking existence of material usage pair."""
    # Seed data has WorkLog 2 with Material 5 (R-410A gas)
    assert repo.work_log_material_exists(2, 5, conn=db_conn) is True
    # Seed data does not have WorkLog 1 with Material 9
    assert repo.work_log_material_exists(1, 9, conn=db_conn) is False


def test_repo_list_material_usage_and_filters(repo, db_conn):
    """Test listing and filtering material usage records."""
    all_usage = repo.list_material_usage(conn=db_conn)
    assert len(all_usage) >= 4

    # Filter by work_log_id = 2
    wl2_usage = repo.list_material_usage({"work_log_id": 2}, conn=db_conn)
    assert len(wl2_usage) == 1
    assert wl2_usage[0]["material_name"] == "R-410A Eco Refrigerant Gas"
    assert wl2_usage[0]["calculated_usage_cost"] == Decimal("2375.00")

    # Filter by material_id = 5
    mat5_usage = repo.list_material_usage({"material_id": 5}, conn=db_conn)
    assert len(mat5_usage) >= 1
    assert all(u["material_id"] == 5 for u in mat5_usage)

    # Filter by request_id = 1 (Request 1 has work log 2 which consumed material 5)
    req1_usage = repo.list_material_usage({"request_id": 1}, conn=db_conn)
    assert len(req1_usage) >= 1
    assert all(u["request_id"] == 1 for u in req1_usage)

    # Filter by technician_id = 3 (Gurpreet Singh)
    tech3_usage = repo.list_material_usage({"technician_id": 3}, conn=db_conn)
    assert len(tech3_usage) >= 1


def test_repo_list_materials(repo, db_conn):
    """Test listing materials catalog items."""
    materials = repo.list_materials(conn=db_conn)
    assert len(materials) == 10

    # Filter by status
    active_mats = repo.list_materials({"status": "Active"}, conn=db_conn)
    assert len(active_mats) == 10

    # Search by name
    pipe_mats = repo.list_materials({"search": "CPVC Pipe"}, conn=db_conn)
    assert len(pipe_mats) == 1
    assert pipe_mats[0]["material_id"] == 3


def test_repo_technician_and_work_log_context(repo, db_conn):
    """Test technician check and work log context resolution."""
    assert repo.technician_exists(1, conn=db_conn) is True
    assert repo.technician_exists(9999, conn=db_conn) is False

    ctx = repo.get_work_log_context(1, conn=db_conn)
    assert ctx is not None
    assert ctx["work_log_id"] == 1
    assert ctx["assignment_id"] == 1
    assert ctx["request_id"] == 1
    assert ctx["request_number"] == "REQ-20260920-0001"

    assert repo.get_work_log_context(9999, conn=db_conn) is None
