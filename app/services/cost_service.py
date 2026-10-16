"""
Cost Service Module
Coordinates financial cost retrieval, filtering, and validation.
Enforces the approved single-ledger model where COST is the authoritative source.
Adheres strictly to the read-only requirement for Phase 3D.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
import psycopg

from app.db import DatabaseManager, get_db_manager
from app.exceptions import (
    CostNotFoundError,
    InvalidCostError,
    InvalidDateError,
    InvalidFilterError,
)
from app.repositories.cost import ALLOWED_COST_TYPES, CostRepository
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CostService:
    """Service layer managing the single financial cost ledger for maintenance requests."""

    def __init__(
        self,
        cost_repo: CostRepository | None = None,
        db_manager: DatabaseManager | None = None,
    ) -> None:
        self.cost_repo = cost_repo or CostRepository()
        self.db_manager = db_manager or get_db_manager()

    def get_cost_by_id(
        self,
        cost_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """Retrieve cost entry by primary key or raise CostNotFoundError."""
        if cost_id is None or not isinstance(cost_id, int) or cost_id <= 0:
            raise InvalidCostError(f"Cost ID must be a positive integer: {cost_id}")

        cost = self.cost_repo.get_cost_by_id(cost_id, conn=conn)
        if not cost:
            raise CostNotFoundError(f"Financial cost record with ID {cost_id} does not exist")
        return cost

    def list_costs(
        self,
        filters: dict[str, Any] | None = None,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """List and filter cost records with validated filter criteria."""
        filters = filters or {}
        limit = filters.get("limit", 100)
        offset = filters.get("offset", 0)

        if not isinstance(limit, int) or limit < 1:
            raise InvalidFilterError("Limit filter must be a positive integer")
        if not isinstance(offset, int) or offset < 0:
            raise InvalidFilterError("Offset filter must be a non-negative integer")

        if "cost_type" in filters and filters["cost_type"] is not None:
            cost_type = filters["cost_type"]
            if cost_type not in ALLOWED_COST_TYPES:
                raise InvalidCostError(
                    f"Invalid cost_type '{cost_type}'. Must be one of: {sorted(list(ALLOWED_COST_TYPES))}"
                )

        if "date_from" in filters and filters["date_from"] is not None:
            if not isinstance(filters["date_from"], datetime):
                raise InvalidDateError("date_from must be a valid datetime instance")

        if "date_to" in filters and filters["date_to"] is not None:
            if not isinstance(filters["date_to"], datetime):
                raise InvalidDateError("date_to must be a valid datetime instance")

        return self.cost_repo.list_costs(filters=filters, conn=conn)
