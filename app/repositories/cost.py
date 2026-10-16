"""
Cost Repository Module
Handles all parameterized data-access operations for the COST entity.
Represents the single recorded financial ledger for facility maintenance expenditures.
Mutation of costs is strictly disabled in Phase 3D to ensure ledger immutability.
"""

from __future__ import annotations

from typing import Any
import psycopg

from app.repositories.base import BaseRepository

ALLOWED_COST_TYPES = frozenset({
    "Material",
    "Labor",
    "Service",
    "Miscellaneous",
})


class CostRepository(BaseRepository):
    """Data access repository for direct maintenance financial expenditures."""

    _BASE_SELECT = """
        SELECT 
            c.cost_id,
            c.request_id,
            r.request_number,
            c.cost_type,
            c.amount,
            c.cost_date,
            c.description
        FROM cost c
        JOIN request r ON c.request_id = r.request_id
    """

    def create_cost(
        self,
        data: dict[str, Any],
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """Insert a new financial ledger cost record."""
        query = """
            INSERT INTO cost (
                request_id,
                cost_type,
                amount,
                cost_date,
                description
            ) VALUES (
                %(request_id)s,
                %(cost_type)s,
                %(amount)s,
                %(cost_date)s,
                %(description)s
            )
            RETURNING 
                cost_id,
                request_id,
                cost_type,
                amount,
                cost_date,
                description;
        """
        row = self.execute_returning(query, data, conn=conn)
        if not row:
            raise RuntimeError("Failed to insert cost record: no row returned")
        return row

    def get_cost_by_id(
        self,
        cost_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve a cost entry by primary key with joined request metadata."""
        query = f"{self._BASE_SELECT} WHERE c.cost_id = %(cost_id)s;"
        return self.fetch_one(query, {"cost_id": cost_id}, conn=conn)

    def list_costs(
        self,
        filters: dict[str, Any] | None = None,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """
        List and filter cost records using parameterized predicates.
        Supports filtering by request_id, cost_type, and date range.
        """
        filters = filters or {}
        conditions: list[str] = []
        params: dict[str, Any] = {}

        if filters.get("request_id") is not None:
            conditions.append("c.request_id = %(request_id)s")
            params["request_id"] = filters["request_id"]

        if filters.get("cost_type"):
            conditions.append("c.cost_type = %(cost_type)s")
            params["cost_type"] = filters["cost_type"]

        if filters.get("date_from") is not None:
            conditions.append("c.cost_date >= %(date_from)s")
            params["date_from"] = filters["date_from"]

        if filters.get("date_to") is not None:
            conditions.append("c.cost_date <= %(date_to)s")
            params["date_to"] = filters["date_to"]

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        limit = int(filters.get("limit", 100))
        offset = int(filters.get("offset", 0))
        params["limit"] = limit
        params["offset"] = offset

        query = f"""
            {self._BASE_SELECT}
            {where_clause}
            ORDER BY c.cost_date DESC, c.cost_id DESC
            LIMIT %(limit)s OFFSET %(offset)s;
        """
        return self.fetch_all(query, params, conn=conn)
