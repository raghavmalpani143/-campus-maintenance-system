"""
Unit & Integration Tests for CostService
Verifies cost retrieval, validation, filtering, and single-ledger integrity.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import pytest

from app.exceptions import (
    CostNotFoundError,
    InvalidCostError,
    InvalidDateError,
    InvalidFilterError,
)
from app.services.cost_service import CostService


@pytest.fixture
def service():
    return CostService()


def test_pos_get_cost_by_id(service, db_conn):
    """Positive: Retrieve existing cost entry by ID."""
    cost = service.get_cost_by_id(1, conn=db_conn)
    assert cost is not None
    assert cost["cost_id"] == 1
    assert cost["request_id"] == 1
    assert cost["cost_type"] == "Material"
    assert cost["amount"] == Decimal("2375.00")
    assert cost["request_number"] == "REQ-20260920-0001"


def test_pos_list_costs_and_filters(service, db_conn):
    """Positive: List costs and apply filters (request_id, cost_type, date range)."""
    costs = service.list_costs(conn=db_conn)
    assert len(costs) >= 12

    # Filter by request_id
    req2_costs = service.list_costs({"request_id": 2}, conn=db_conn)
    assert len(req2_costs) == 3
    assert all(c["request_id"] == 2 for c in req2_costs)

    # Filter by cost_type
    material_costs = service.list_costs({"cost_type": "Material"}, conn=db_conn)
    assert len(material_costs) >= 3
    assert all(c["cost_type"] == "Material" for c in material_costs)

    # Filter by date range
    d_from = datetime(2026, 9, 20, 0, 0, 0)
    d_to = datetime(2026, 9, 21, 23, 59, 59)
    date_filtered = service.list_costs({"date_from": d_from, "date_to": d_to}, conn=db_conn)
    assert len(date_filtered) >= 6


def test_neg_cost_not_found(service, db_conn):
    """Negative: Nonexistent cost ID raises CostNotFoundError."""
    with pytest.raises(CostNotFoundError, match="Financial cost record with ID 99999 does not exist"):
        service.get_cost_by_id(99999, conn=db_conn)


def test_neg_invalid_cost_id(service, db_conn):
    """Negative: Invalid cost ID raises InvalidCostError."""
    with pytest.raises(InvalidCostError, match="Cost ID must be a positive integer"):
        service.get_cost_by_id(0, conn=db_conn)

    with pytest.raises(InvalidCostError, match="Cost ID must be a positive integer"):
        service.get_cost_by_id(-5, conn=db_conn)

    with pytest.raises(InvalidCostError, match="Cost ID must be a positive integer"):
        service.get_cost_by_id("invalid", conn=db_conn)  # type: ignore


def test_neg_invalid_cost_type_filter(service, db_conn):
    """Negative: Invalid cost_type filter raises InvalidCostError."""
    with pytest.raises(InvalidCostError, match="Invalid cost_type 'UnapprovedType'"):
        service.list_costs({"cost_type": "UnapprovedType"}, conn=db_conn)


def test_neg_invalid_filters(service, db_conn):
    """Negative: Invalid pagination or date filters raise appropriate errors."""
    with pytest.raises(InvalidFilterError, match="Limit filter must be a positive integer"):
        service.list_costs({"limit": 0}, conn=db_conn)

    with pytest.raises(InvalidFilterError, match="Offset filter must be a non-negative integer"):
        service.list_costs({"offset": -1}, conn=db_conn)

    with pytest.raises(InvalidDateError, match="date_from must be a valid datetime instance"):
        service.list_costs({"date_from": "not-a-datetime"}, conn=db_conn)  # type: ignore

    with pytest.raises(InvalidDateError, match="date_to must be a valid datetime instance"):
        service.list_costs({"date_to": "not-a-datetime"}, conn=db_conn)  # type: ignore
