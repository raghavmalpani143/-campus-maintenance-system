"""
Work Log Repository Module
Handles all parameterized data-access operations for the WORK_LOG entity.
Strictly encapsulates SQL logic and executes joins through ASSIGNMENT to REQUEST and TECHNICIAN.
"""

from __future__ import annotations

from typing import Any
import psycopg

from app.repositories.base import BaseRepository

# Explicit whitelist of work log fields permitted to be directly updated
ALLOWED_WORK_LOG_UPDATE_FIELDS = frozenset({
    "work_description",
    "hours_spent",
    "work_date",
})


class WorkLogRepository(BaseRepository):
    """Data access repository for work log entries."""

    _BASE_SELECT = """
        SELECT 
            wl.work_log_id,
            wl.assignment_id,
            a.request_id,
            r.request_number,
            a.technician_id,
            t.full_name AS technician_name,
            t.department AS technician_department,
            t.labor_rate AS technician_labor_rate,
            wl.work_date,
            wl.work_description,
            wl.hours_spent
        FROM work_log wl
        JOIN assignment a ON wl.assignment_id = a.assignment_id
        JOIN request r ON a.request_id = r.request_id
        JOIN technician t ON a.technician_id = t.technician_id
    """

    def create_work_log(
        self,
        data: dict[str, Any],
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """Insert a new work log record."""
        query = """
            INSERT INTO work_log (
                assignment_id,
                work_date,
                work_description,
                hours_spent
            ) VALUES (
                %(assignment_id)s,
                %(work_date)s,
                %(work_description)s,
                %(hours_spent)s
            )
            RETURNING 
                work_log_id,
                assignment_id,
                work_date,
                work_description,
                hours_spent;
        """
        row = self.execute_returning(query, data, conn=conn)
        if not row:
            raise RuntimeError("Failed to insert work_log record: no row returned")
        return row

    def get_by_id(
        self,
        work_log_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve a work log by primary key with joined assignment, request, and technician metadata."""
        query = f"{self._BASE_SELECT} WHERE wl.work_log_id = %(work_log_id)s"
        return self.fetch_one(query, {"work_log_id": work_log_id}, conn=conn)

    def list_work_logs(
        self,
        filters: dict[str, Any] | None = None,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """
        List and filter work logs using parameterized predicates.
        Supports filtering by assignment_id, request_id, technician_id, and date bounds.
        """
        filters = filters or {}
        conditions: list[str] = []
        params: dict[str, Any] = {}

        if filters.get("assignment_id") is not None:
            conditions.append("wl.assignment_id = %(assignment_id)s")
            params["assignment_id"] = filters["assignment_id"]

        if filters.get("request_id") is not None:
            conditions.append("a.request_id = %(request_id)s")
            params["request_id"] = filters["request_id"]

        if filters.get("technician_id") is not None:
            conditions.append("a.technician_id = %(technician_id)s")
            params["technician_id"] = filters["technician_id"]

        if filters.get("date_from") is not None:
            conditions.append("wl.work_date >= %(date_from)s")
            params["date_from"] = filters["date_from"]

        if filters.get("date_to") is not None:
            conditions.append("wl.work_date <= %(date_to)s")
            params["date_to"] = filters["date_to"]

        if filters.get("search"):
            conditions.append("wl.work_description ILIKE %(search)s")
            params["search"] = f"%{filters['search']}%"

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        limit = int(filters.get("limit", 100))
        offset = int(filters.get("offset", 0))
        params["limit"] = limit
        params["offset"] = offset

        query = f"""
            {self._BASE_SELECT}
            {where_clause}
            ORDER BY wl.work_log_id DESC
            LIMIT %(limit)s OFFSET %(offset)s
        """
        return self.fetch_all(query, params, conn=conn)

    def update_work_log(
        self,
        work_log_id: int,
        updates: dict[str, Any],
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Update explicitly permitted fields on a work log record."""
        filtered_updates = {k: v for k, v in updates.items() if k in ALLOWED_WORK_LOG_UPDATE_FIELDS}
        if not filtered_updates:
            return self.get_by_id(work_log_id, conn=conn)

        set_clauses: list[str] = []
        params: dict[str, Any] = {"work_log_id": work_log_id}

        for col, val in filtered_updates.items():
            set_clauses.append(f"{col} = %({col})s")
            params[col] = val

        query = f"""
            UPDATE work_log
            SET {', '.join(set_clauses)}
            WHERE work_log_id = %(work_log_id)s
            RETURNING work_log_id;
        """
        row = self.execute_returning(query, params, conn=conn)
        if not row:
            return None
        return self.get_by_id(work_log_id, conn=conn)

    def assignment_exists(self, assignment_id: int, conn: psycopg.Connection | None = None) -> bool:
        """Check whether an assignment exists."""
        query = "SELECT 1 AS found FROM assignment WHERE assignment_id = %(assignment_id)s"
        return self.fetch_one(query, {"assignment_id": assignment_id}, conn=conn) is not None

    def get_assignment(self, assignment_id: int, conn: psycopg.Connection | None = None) -> dict[str, Any] | None:
        """Retrieve assignment record."""
        query = "SELECT assignment_id, request_id, technician_id, assigned_date, due_date, status FROM assignment WHERE assignment_id = %(assignment_id)s"
        return self.fetch_one(query, {"assignment_id": assignment_id}, conn=conn)
