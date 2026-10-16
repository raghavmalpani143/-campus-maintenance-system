"""
Material & Material Usage Repository Module
Handles all parameterized data-access operations for MATERIAL and WORK_LOG_MATERIAL.
Strictly encapsulates SQL logic, uses row-level locking for inventory safety,
and returns explicit joined projections without storing redundant columns.
"""

from __future__ import annotations

from typing import Any
import psycopg

from app.repositories.base import BaseRepository


class MaterialRepository(BaseRepository):
    """Data access repository for materials, warehouse stock, and work log material usage."""

    _BASE_USAGE_SELECT = """
        SELECT 
            wlm.work_log_id,
            wlm.material_id,
            wlm.quantity_used,
            wlm.issued_date,
            wlm.issued_by,
            it.full_name AS issued_by_name,
            it.full_name AS technician_name,
            m.material_name,
            m.unit AS material_unit,
            COALESCE(c.amount / NULLIF(wlm.quantity_used, 0), m.unit_cost) AS unit_cost,
            COALESCE(c.amount / NULLIF(wlm.quantity_used, 0), m.unit_cost) AS unit_price,
            COALESCE(c.amount, ROUND(wlm.quantity_used * m.unit_cost, 2)) AS calculated_usage_cost,
            COALESCE(c.amount, ROUND(wlm.quantity_used * m.unit_cost, 2)) AS total_cost,
            c.cost_id,
            wl.assignment_id,
            a.request_id,
            r.request_number,
            at.technician_id AS assigned_technician_id,
            at.full_name AS assigned_technician_name
        FROM work_log_material wlm
        JOIN material m ON wlm.material_id = m.material_id
        JOIN technician it ON wlm.issued_by = it.technician_id
        JOIN work_log wl ON wlm.work_log_id = wl.work_log_id
        JOIN assignment a ON wl.assignment_id = a.assignment_id
        JOIN technician at ON a.technician_id = at.technician_id
        JOIN request r ON a.request_id = r.request_id
        LEFT JOIN LATERAL (
            SELECT c_sub.cost_id, c_sub.amount 
            FROM cost c_sub 
            WHERE c_sub.request_id = r.request_id 
              AND c_sub.cost_type = 'Material'
              AND (
                c_sub.description LIKE '%%[WLM:' || wlm.work_log_id || ':' || wlm.material_id || ']%%'
                OR (c_sub.description NOT LIKE '%%[WLM:%%' AND c_sub.description ILIKE '%%' || m.material_name || '%%')
              )
            ORDER BY c_sub.cost_id DESC 
            LIMIT 1
        ) c ON true
    """

    def get_material_by_id(
        self,
        material_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve material catalog record by primary key."""
        query = """
            SELECT 
                material_id,
                material_name,
                unit,
                unit_cost,
                stock_qty,
                status
            FROM material
            WHERE material_id = %(material_id)s;
        """
        return self.fetch_one(query, {"material_id": material_id}, conn=conn)

    def get_material_for_update(
        self,
        material_id: int,
        conn: psycopg.Connection,
    ) -> dict[str, Any] | None:
        """
        Retrieve material catalog record with exclusive row-level lock (FOR UPDATE).
        Must be executed within an active transaction to guarantee stock concurrency safety.
        """
        query = """
            SELECT 
                material_id,
                material_name,
                unit,
                unit_cost,
                stock_qty,
                status
            FROM material
            WHERE material_id = %(material_id)s
            FOR UPDATE;
        """
        return self.fetch_one(query, {"material_id": material_id}, conn=conn)

    def decrement_stock(
        self,
        material_id: int,
        quantity: Any,
        conn: psycopg.Connection,
    ) -> dict[str, Any] | None:
        """
        Atomically decrement stock for a material item within an active transaction.
        Relies on chk_material_stock_qty constraint to guarantee stock never becomes negative.
        """
        query = """
            UPDATE material
            SET stock_qty = stock_qty - %(quantity)s
            WHERE material_id = %(material_id)s
            RETURNING 
                material_id,
                material_name,
                unit,
                unit_cost,
                stock_qty,
                status;
        """
        return self.execute_returning(
            query,
            {"material_id": material_id, "quantity": quantity},
            conn=conn,
        )

    def create_work_log_material(
        self,
        data: dict[str, Any],
        conn: psycopg.Connection,
    ) -> dict[str, Any]:
        """Insert a WORK_LOG_MATERIAL junction row within an active transaction."""
        query = """
            INSERT INTO work_log_material (
                work_log_id,
                material_id,
                quantity_used,
                issued_date,
                issued_by
            ) VALUES (
                %(work_log_id)s,
                %(material_id)s,
                %(quantity_used)s,
                %(issued_date)s,
                %(issued_by)s
            )
            RETURNING 
                work_log_id,
                material_id,
                quantity_used,
                issued_date,
                issued_by;
        """
        row = self.execute_returning(query, data, conn=conn)
        if not row:
            raise RuntimeError("Failed to insert work_log_material record: no row returned")
        return row

    def work_log_material_exists(
        self,
        work_log_id: int,
        material_id: int,
        conn: psycopg.Connection | None = None,
    ) -> bool:
        """Check whether material has already been issued for a specific work log."""
        query = """
            SELECT 1 AS found
            FROM work_log_material
            WHERE work_log_id = %(work_log_id)s AND material_id = %(material_id)s;
        """
        return self.fetch_one(
            query,
            {"work_log_id": work_log_id, "material_id": material_id},
            conn=conn,
        ) is not None

    def get_material_usage(
        self,
        work_log_id: int,
        material_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve a specific material usage entry by composite key with joined request & technician details."""
        query = f"""
            {self._BASE_USAGE_SELECT}
            WHERE wlm.work_log_id = %(work_log_id)s AND wlm.material_id = %(material_id)s;
        """
        return self.fetch_one(
            query,
            {"work_log_id": work_log_id, "material_id": material_id},
            conn=conn,
        )

    def list_material_usage(
        self,
        filters: dict[str, Any] | None = None,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """
        List and filter material usage entries using parameterized predicates.
        Supports filtering by work_log_id, material_id, request_id, technician_id, issued_by, and date range.
        """
        filters = filters or {}
        conditions: list[str] = []
        params: dict[str, Any] = {}

        if filters.get("work_log_id") is not None:
            conditions.append("wlm.work_log_id = %(work_log_id)s")
            params["work_log_id"] = filters["work_log_id"]

        if filters.get("material_id") is not None:
            conditions.append("wlm.material_id = %(material_id)s")
            params["material_id"] = filters["material_id"]

        if filters.get("request_id") is not None:
            conditions.append("a.request_id = %(request_id)s")
            params["request_id"] = filters["request_id"]

        if filters.get("issued_by") is not None:
            conditions.append("wlm.issued_by = %(issued_by)s")
            params["issued_by"] = filters["issued_by"]

        if filters.get("technician_id") is not None:
            # Matches either the technician who requisitioned it or the assigned technician
            conditions.append("(wlm.issued_by = %(technician_id)s OR a.technician_id = %(technician_id)s)")
            params["technician_id"] = filters["technician_id"]

        if filters.get("date_from") is not None:
            conditions.append("wlm.issued_date >= %(date_from)s")
            params["date_from"] = filters["date_from"]

        if filters.get("date_to") is not None:
            conditions.append("wlm.issued_date <= %(date_to)s")
            params["date_to"] = filters["date_to"]

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        limit = int(filters.get("limit", 100))
        offset = int(filters.get("offset", 0))
        params["limit"] = limit
        params["offset"] = offset

        query = f"""
            {self._BASE_USAGE_SELECT}
            {where_clause}
            ORDER BY wlm.issued_date DESC, wlm.work_log_id DESC, wlm.material_id DESC
            LIMIT %(limit)s OFFSET %(offset)s;
        """
        return self.fetch_all(query, params, conn=conn)

    def list_materials(
        self,
        filters: dict[str, Any] | None = None,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """List materials from the catalog with optional status and name search filters."""
        filters = filters or {}
        conditions: list[str] = []
        params: dict[str, Any] = {}

        if filters.get("status"):
            conditions.append("status = %(status)s")
            params["status"] = filters["status"]

        if filters.get("search"):
            conditions.append("material_name ILIKE %(search)s")
            params["search"] = f"%{filters['search']}%"

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        limit = int(filters.get("limit", 100))
        offset = int(filters.get("offset", 0))
        params["limit"] = limit
        params["offset"] = offset

        query = f"""
            SELECT 
                material_id,
                material_name,
                unit,
                unit_cost,
                stock_qty,
                status
            FROM material
            {where_clause}
            ORDER BY material_id ASC
            LIMIT %(limit)s OFFSET %(offset)s;
        """
        return self.fetch_all(query, params, conn=conn)

    def technician_exists(
        self,
        technician_id: int,
        conn: psycopg.Connection | None = None,
    ) -> bool:
        """Check whether a technician exists in the database."""
        query = "SELECT 1 AS found FROM technician WHERE technician_id = %(technician_id)s;"
        return self.fetch_one(query, {"technician_id": technician_id}, conn=conn) is not None

    def get_work_log_context(
        self,
        work_log_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """
        Retrieve work log and resolve its associated request_id and request_number via ASSIGNMENT.
        Returns None if work_log_id does not exist.
        """
        query = """
            SELECT 
                wl.work_log_id,
                wl.assignment_id,
                wl.work_date,
                a.request_id,
                r.request_number,
                a.technician_id AS assigned_technician_id,
                t.full_name AS assigned_technician_name
            FROM work_log wl
            JOIN assignment a ON wl.assignment_id = a.assignment_id
            JOIN request r ON a.request_id = r.request_id
            JOIN technician t ON a.technician_id = t.technician_id
            WHERE wl.work_log_id = %(work_log_id)s;
        """
        return self.fetch_one(query, {"work_log_id": work_log_id}, conn=conn)

    def get_material_by_name(
        self,
        material_name: str,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Find a material by case-insensitive name match."""
        query = """
            SELECT material_id, material_name, unit, unit_cost, stock_qty, status
            FROM material
            WHERE LOWER(TRIM(material_name)) = LOWER(TRIM(%(material_name)s))
            LIMIT 1;
        """
        return self.fetch_one(query, {"material_name": material_name}, conn=conn)

    def create_material(
        self,
        data: dict[str, Any],
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """Insert a new material catalog record."""
        query = """
            INSERT INTO material (
                material_name,
                unit,
                unit_cost,
                stock_qty,
                status
            ) VALUES (
                %(material_name)s,
                %(unit)s,
                %(unit_cost)s,
                %(stock_qty)s,
                %(status)s
            )
            RETURNING 
                material_id,
                material_name,
                unit,
                unit_cost,
                stock_qty,
                status;
        """
        row = self.execute_returning(query, data, conn=conn)
        if not row:
            raise RuntimeError("Failed to insert material catalog row: no row returned")
        return row

    def restock_material(
        self,
        material_id: int,
        quantity: int | float | Any,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """Replenish warehouse stock for a material."""
        query = """
            UPDATE material
            SET stock_qty = stock_qty + %(quantity)s
            WHERE material_id = %(material_id)s
            RETURNING material_id, material_name, unit, unit_cost, stock_qty, status;
        """
        row = self.execute_returning(query, {"material_id": material_id, "quantity": quantity}, conn=conn)
        if not row:
            raise RuntimeError(f"Failed to restock material ID {material_id}")
        return row
