"""
Unit & Integration Tests for CostRepository
Verifies parameterized SQL execution, single-ledger COST operations,
and relational joins with REQUEST.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import pytest

from app.repositories.cost import CostRepository


@pytest.fixture
def repo():
    return CostRepository()


def test_repo_create_and_get_cost(repo, db_conn):
    """Test inserting and retrieving a financial cost ledger record."""
    now = datetime(2026, 10, 1, 12, 0, 0)
    created = repo.create_cost(
        {
            "request_id": 1,
            "cost_type": "Material",
            "amount": Decimal("540.00"),
            "cost_date": now,
            "description": "3x Philips 20W LED Tubes replacement",
        },
        conn=db_conn,
    )
    assert created["cost_id"] is not None
    assert created["request_id"] == 1
    assert created["cost_type"] == "Material"
    assert created["amount"] == Decimal("540.00")

    retrieved = repo.get_cost_by_id(created["cost_id"], conn=db_conn)
    assert retrieved is not None
    assert retrieved["cost_id"] == created["cost_id"]
    assert retrieved["request_id"] == 1
    assert retrieved["request_number"] == "REQ-20260920-0001"
    assert retrieved["cost_type"] == "Material"
    assert retrieved["amount"] == Decimal("540.00")
    assert retrieved["description"] == "3x Philips 20W LED Tubes replacement"


def test_repo_get_cost_nonexistent(repo, db_conn):
    """Test retrieving nonexistent cost ID returns None."""
    assert repo.get_cost_by_id(99999, conn=db_conn) is None


def test_repo_list_costs_and_filters(repo, db_conn):
    """Test listing and filtering cost records across requests, types, and dates."""
    all_costs = repo.list_costs(conn=db_conn)
    assert len(all_costs) >= 12

    # Filter by request_id = 1 (Request 1 has 3 seeded costs: Material, Labor, Service)
    req1_costs = repo.list_costs({"request_id": 1}, conn=db_conn)
    assert len(req1_costs) == 3
    assert all(c["request_id"] == 1 for c in req1_costs)
    assert all(c["request_number"] == "REQ-20260920-0001" for c in req1_costs)

    # Filter by cost_type = 'Material' (Seed data has 3 Material costs)
    material_costs = repo.list_costs({"cost_type": "Material"}, conn=db_conn)
    assert len(material_costs) >= 3
    assert all(c["cost_type"] == "Material" for c in material_costs)

    # Filter by cost_type = 'Labor' (Seed data has 5 Labor costs)
    labor_costs = repo.list_costs({"cost_type": "Labor"}, conn=db_conn)
    assert len(labor_costs) >= 5
    assert all(c["cost_type"] == "Labor" for c in labor_costs)

    # Filter by date range
    d_from = datetime(2026, 9, 20, 0, 0, 0)
    d_to = datetime(2026, 9, 21, 23, 59, 59)
    date_costs = repo.list_costs({"date_from": d_from, "date_to": d_to}, conn=db_conn)
    assert len(date_costs) >= 6
