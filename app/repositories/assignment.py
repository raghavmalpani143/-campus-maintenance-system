"""
Assignment Repository Module
Handles all parameterized data-access operations for the ASSIGNMENT entity.
Strictly encapsulates SQL logic and executes joins with REQUEST and TECHNICIAN.
"""

from __future__ import annotations

from typing import Any
import psycopg

from app.repositories.base import BaseRepository

# Explicit whitelist of assignment fields permitted to be directly updated
ALLOWED_ASSIGNMENT_UPDATE_FIELDS = frozenset({
    "status",
    "due_date",
})


class AssignmentRepository(BaseRepository):
    """Data access repository for technician assignments."""

    _BASE_SELECT = """
        SELECT 
            a.assignment_id,
            a.request_id,
            r.request_number,
            r.description AS request_description,
            r.status_id AS request_status_id,
            rs.status_name AS request_status_name,
            a.technician_id,
            t.full_name AS technician_name,
            t.department AS technician_department,
            t.labor_rate AS technician_labor_rate,
            t.status AS technician_status,
            a.assigned_date,
            a.due_date,
            a.status AS assignment_status
        FROM assignment a
        JOIN request r ON a.request_id = r.request_id
        JOIN status rs ON r.status_id = rs.status_id
        JOIN technician t ON a.technician_id = t.technician_id
    """

    def create_assignment(
        self,
        data: dict[str, Any],
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """Insert a new technician assignment record."""
        query = """
            INSERT INTO assignment (
                request_id,
                technician_id,
                assigned_date,
                due_date,
                status
            ) VALUES (
                %(request_id)s,
                %(technician_id)s,
                %(assigned_date)s,
                %(due_date)s,
                %(status)s
            )
            RETURNING 
                assignment_id,
                request_id,
                technician_id,
                assigned_date,
                due_date,
                status;
        """
        row = self.execute_returning(query, data, conn=conn)
        if not row:
            raise RuntimeError("Failed to insert assignment record: no row returned")
        return row

    def get_by_id(
        self,
        assignment_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve an assignment by primary key with joined request and technician metadata."""
        query = f"{self._BASE_SELECT} WHERE a.assignment_id = %(assignment_id)s"
        return self.fetch_one(query, {"assignment_id": assignment_id}, conn=conn)

    def list_assignments(
        self,
        filters: dict[str, Any] | None = None,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """
        List and filter assignments using parameterized predicates.
        Supports filtering by request_id, technician_id, status, and date bounds.
        """
        filters = filters or {}
        conditions: list[str] = []
        params: dict[str, Any] = {}

        if filters.get("request_id") is not None:
            conditions.append("a.request_id = %(request_id)s")
            params["request_id"] = filters["request_id"]

        if filters.get("technician_id") is not None:
            conditions.append("a.technician_id = %(technician_id)s")
            params["technician_id"] = filters["technician_id"]

        if filters.get("status") is not None:
            conditions.append("a.status = %(status)s")
            params["status"] = filters["status"]

        if filters.get("assigned_date_from") is not None:
            conditions.append("a.assigned_date >= %(assigned_date_from)s")
            params["assigned_date_from"] = filters["assigned_date_from"]

        if filters.get("assigned_date_to") is not None:
            conditions.append("a.assigned_date <= %(assigned_date_to)s")
            params["assigned_date_to"] = filters["assigned_date_to"]

        if filters.get("due_date_from") is not None:
            conditions.append("a.due_date >= %(due_date_from)s")
            params["due_date_from"] = filters["due_date_from"]

        if filters.get("due_date_to") is not None:
            conditions.append("a.due_date <= %(due_date_to)s")
            params["due_date_to"] = filters["due_date_to"]

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        limit = int(filters.get("limit", 100))
        offset = int(filters.get("offset", 0))
        params["limit"] = limit
        params["offset"] = offset

        query = f"""
            {self._BASE_SELECT}
            {where_clause}
            ORDER BY a.assignment_id DESC
            LIMIT %(limit)s OFFSET %(offset)s
        """
        return self.fetch_all(query, params, conn=conn)

    def update_assignment(
        self,
        assignment_id: int,
        updates: dict[str, Any],
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Update explicitly permitted fields on an assignment record."""
        filtered_updates = {k: v for k, v in updates.items() if k in ALLOWED_ASSIGNMENT_UPDATE_FIELDS}
        if not filtered_updates:
            return self.get_by_id(assignment_id, conn=conn)

        set_clauses: list[str] = []
        params: dict[str, Any] = {"assignment_id": assignment_id}

        for col, val in filtered_updates.items():
            set_clauses.append(f"{col} = %({col})s")
            params[col] = val

        query = f"""
            UPDATE assignment
            SET {', '.join(set_clauses)}
            WHERE assignment_id = %(assignment_id)s
            RETURNING assignment_id;
        """
        row = self.execute_returning(query, params, conn=conn)
        if not row:
            return None
        return self.get_by_id(assignment_id, conn=conn)

    def request_exists(self, request_id: int, conn: psycopg.Connection | None = None) -> bool:
        """Check whether a maintenance request exists."""
        query = "SELECT 1 AS found FROM request WHERE request_id = %(request_id)s"
        return self.fetch_one(query, {"request_id": request_id}, conn=conn) is not None

    def technician_exists(self, technician_id: int, conn: psycopg.Connection | None = None) -> bool:
        """Check whether a technician exists."""
        query = "SELECT 1 AS found FROM technician WHERE technician_id = %(technician_id)s"
        return self.fetch_one(query, {"technician_id": technician_id}, conn=conn) is not None

    def get_technician(self, technician_id: int, conn: psycopg.Connection | None = None) -> dict[str, Any] | None:
        """Retrieve technician details."""
        query = "SELECT technician_id, full_name, department, status, labor_rate FROM technician WHERE technician_id = %(technician_id)s"
        return self.fetch_one(query, {"technician_id": technician_id}, conn=conn)
