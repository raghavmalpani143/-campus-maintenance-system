"""
Request Repository Module
Handles all parameterized data-access operations for the REQUEST and STATUS_HISTORY entities.
Strictly encapsulates SQL logic and executes joins to retrieve rich related data.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Sequence
import psycopg

from app.repositories.base import BaseRepository

# Explicit whitelist of request fields permitted to be directly updated in Phase 3B
ALLOWED_UPDATE_FIELDS = frozenset({
    "description",
    "category_id",
    "priority_id",
    "room_id",
    "asset_id",
})


class RequestRepository(BaseRepository):
    """Data access repository for maintenance requests and status history."""

    _BASE_SELECT = """
        SELECT 
            r.request_id,
            r.request_number,
            r.request_date,
            r.description,
            r.category_id,
            c.category_name,
            r.priority_id,
            p.priority_level,
            p.response_time_hr AS sla_response_time_hr,
            r.requested_by,
            u.full_name AS requester_name,
            u.email AS requester_email,
            r.room_id,
            rm.room_number,
            rm.floor AS room_floor,
            rm.room_type,
            b.building_id,
            b.building_name,
            b.location AS building_location,
            r.asset_id,
            a.asset_name,
            a.asset_type,
            a.brand_model AS asset_brand_model,
            r.status_id,
            s.status_name,
            r.closed_date,
            r.resolution_description,
            r.closed_by,
            cb.full_name AS closed_by_name
        FROM request r
        JOIN category c ON r.category_id = c.category_id
        JOIN priority p ON r.priority_id = p.priority_id
        JOIN "user" u ON r.requested_by = u.user_id
        JOIN room rm ON r.room_id = rm.room_id
        JOIN building b ON rm.building_id = b.building_id
        JOIN status s ON r.status_id = s.status_id
        LEFT JOIN asset a ON r.asset_id = a.asset_id
        LEFT JOIN "user" cb ON r.closed_by = cb.user_id
    """

    # -------------------------------------------------------------------------
    # Core Request CRUD Primitives
    # -------------------------------------------------------------------------

    def create_request(
        self,
        data: dict[str, Any],
        conn: psycopg.Connection,
    ) -> dict[str, Any]:
        """
        Insert a new maintenance request record.
        Must be executed within an active transaction connection.
        """
        query = """
            INSERT INTO request (
                request_number,
                request_date,
                description,
                category_id,
                priority_id,
                requested_by,
                room_id,
                asset_id,
                status_id
            ) VALUES (
                %(request_number)s,
                %(request_date)s,
                %(description)s,
                %(category_id)s,
                %(priority_id)s,
                %(requested_by)s,
                %(room_id)s,
                %(asset_id)s,
                %(status_id)s
            )
            RETURNING 
                request_id,
                request_number,
                request_date,
                description,
                category_id,
                priority_id,
                requested_by,
                room_id,
                asset_id,
                status_id;
        """
        row = self.execute_returning(query, data, conn=conn)
        if not row:
            raise RuntimeError("Failed to insert request record: no row returned")
        return row

    def create_status_history(
        self,
        data: dict[str, Any],
        conn: psycopg.Connection,
    ) -> dict[str, Any]:
        """
        Insert an audit row into the status_history table.
        Must be executed within an active transaction connection.
        """
        query = """
            INSERT INTO status_history (
                request_id,
                status_id,
                changed_by,
                changed_date,
                remarks
            ) VALUES (
                %(request_id)s,
                %(status_id)s,
                %(changed_by)s,
                %(changed_date)s,
                %(remarks)s
            )
            RETURNING 
                status_history_id,
                request_id,
                status_id,
                changed_by,
                changed_date,
                remarks;
        """
        row = self.execute_returning(query, data, conn=conn)
        if not row:
            raise RuntimeError("Failed to insert status_history record: no row returned")
        return row

    def get_by_id(
        self,
        request_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve a single request by its primary key with complete join metadata."""
        query = f"{self._BASE_SELECT} WHERE r.request_id = %(request_id)s"
        return self.fetch_one(query, {"request_id": request_id}, conn=conn)

    def get_by_request_number(
        self,
        request_number: str,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve a single request by its unique request number with complete join metadata."""
        query = f"{self._BASE_SELECT} WHERE r.request_number = %(request_number)s"
        return self.fetch_one(query, {"request_number": request_number}, conn=conn)

    def list_requests(
        self,
        filters: dict[str, Any] | None = None,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search and filter requests using parameterized predicates and relational joins.
        Supports status, priority, category, requester, room, building, date ranges, and text search.
        """
        filters = filters or {}
        conditions: list[str] = []
        params: dict[str, Any] = {}

        if filters.get("status_id") is not None:
            conditions.append("r.status_id = %(status_id)s")
            params["status_id"] = filters["status_id"]

        if filters.get("priority_id") is not None:
            conditions.append("r.priority_id = %(priority_id)s")
            params["priority_id"] = filters["priority_id"]

        if filters.get("category_id") is not None:
            conditions.append("r.category_id = %(category_id)s")
            params["category_id"] = filters["category_id"]

        if filters.get("requested_by") is not None:
            conditions.append("r.requested_by = %(requested_by)s")
            params["requested_by"] = filters["requested_by"]

        if filters.get("room_id") is not None:
            conditions.append("r.room_id = %(room_id)s")
            params["room_id"] = filters["room_id"]

        # Filter by building using the relational path: room.building_id -> building
        if filters.get("building_id") is not None:
            conditions.append("rm.building_id = %(building_id)s")
            params["building_id"] = filters["building_id"]

        if filters.get("date_from") is not None:
            conditions.append("r.request_date >= %(date_from)s")
            params["date_from"] = filters["date_from"]

        if filters.get("date_to") is not None:
            conditions.append("r.request_date <= %(date_to)s")
            params["date_to"] = filters["date_to"]

        if filters.get("search"):
            conditions.append("(r.description ILIKE %(search)s OR r.request_number ILIKE %(search)s)")
            params["search"] = f"%{filters['search']}%"

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        limit = int(filters.get("limit", 100))
        offset = int(filters.get("offset", 0))
        params["limit"] = limit
        params["offset"] = offset

        query = f"""
            {self._BASE_SELECT}
            {where_clause}
            ORDER BY r.request_id DESC
            LIMIT %(limit)s OFFSET %(offset)s
        """
        return self.fetch_all(query, params, conn=conn)

    def update_request(
        self,
        request_id: int,
        updates: dict[str, Any],
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """
        Update explicitly permitted mutable fields for a request.
        Restricted to ALLOWED_UPDATE_FIELDS whitelist.
        """
        filtered_updates = {k: v for k, v in updates.items() if k in ALLOWED_UPDATE_FIELDS}
        if not filtered_updates:
            return self.get_by_id(request_id, conn=conn)

        set_clauses: list[str] = []
        params: dict[str, Any] = {"request_id": request_id}

        for col, val in filtered_updates.items():
            set_clauses.append(f"{col} = %({col})s")
            params[col] = val

        query = f"""
            UPDATE request
            SET {', '.join(set_clauses)}
            WHERE request_id = %(request_id)s
            RETURNING request_id;
        """
        row = self.execute_returning(query, params, conn=conn)
        if not row:
            return None
        return self.get_by_id(request_id, conn=conn)

    # -------------------------------------------------------------------------
    # Integrity & Lookup Helper Primitives
    # -------------------------------------------------------------------------

    def exists_by_request_number(
        self,
        request_number: str,
        conn: psycopg.Connection | None = None,
    ) -> bool:
        """Check whether a request number is already registered."""
        query = "SELECT 1 AS found FROM request WHERE request_number = %(request_number)s"
        row = self.fetch_one(query, {"request_number": request_number}, conn=conn)
        return row is not None

    def get_status_history_for_request(
        self,
        request_id: int,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve complete status audit trail for a specific request."""
        query = """
            SELECT 
                sh.status_history_id,
                sh.request_id,
                sh.status_id,
                s.status_name,
                sh.changed_by,
                u.full_name AS changed_by_name,
                sh.changed_date,
                sh.remarks
            FROM status_history sh
            JOIN status s ON sh.status_id = s.status_id
            JOIN "user" u ON sh.changed_by = u.user_id
            WHERE sh.request_id = %(request_id)s
            ORDER BY sh.status_history_id ASC;
        """
        return self.fetch_all(query, {"request_id": request_id}, conn=conn)

    # Alias for get_status_history_for_request for status audit retrieval
    get_status_history = get_status_history_for_request

    def get_next_sequence_for_date(
        self,
        date_str: str,
        conn: psycopg.Connection | None = None,
    ) -> int:
        """
        Calculate next 4-digit sequence number for formatted request numbers: REQ-YYYYMMDD-XXXX.
        """
        pattern = f"REQ-{date_str}-%"
        query = """
            SELECT request_number 
            FROM request 
            WHERE request_number LIKE %(pattern)s 
            ORDER BY request_number DESC 
            LIMIT 1;
        """
        row = self.fetch_one(query, {"pattern": pattern}, conn=conn)
        if not row:
            return 1

        match = re.search(r"-(\d{4})$", row["request_number"])
        if match:
            return int(match.group(1)) + 1
        return 1

    def user_exists(self, user_id: int, conn: psycopg.Connection | None = None) -> bool:
        """Verify whether a user exists."""
        query = "SELECT 1 AS found FROM \"user\" WHERE user_id = %(user_id)s"
        return self.fetch_one(query, {"user_id": user_id}, conn=conn) is not None

    def category_exists(self, category_id: int, conn: psycopg.Connection | None = None) -> bool:
        """Verify whether a category exists."""
        query = "SELECT 1 AS found FROM category WHERE category_id = %(category_id)s"
        return self.fetch_one(query, {"category_id": category_id}, conn=conn) is not None

    def priority_exists(self, priority_id: int, conn: psycopg.Connection | None = None) -> bool:
        """Verify whether a priority exists."""
        query = "SELECT 1 AS found FROM priority WHERE priority_id = %(priority_id)s"
        return self.fetch_one(query, {"priority_id": priority_id}, conn=conn) is not None

    def room_exists(self, room_id: int, conn: psycopg.Connection | None = None) -> bool:
        """Verify whether a room exists."""
        query = "SELECT 1 AS found FROM room WHERE room_id = %(room_id)s"
        return self.fetch_one(query, {"room_id": room_id}, conn=conn) is not None

    def get_asset(self, asset_id: int, conn: psycopg.Connection | None = None) -> dict[str, Any] | None:
        """Retrieve asset record to verify existence and room location."""
        query = "SELECT asset_id, asset_name, room_id, status FROM asset WHERE asset_id = %(asset_id)s"
        return self.fetch_one(query, {"asset_id": asset_id}, conn=conn)

    # -------------------------------------------------------------------------
    # Status Management Repository Primitives (Phase 3E)
    # -------------------------------------------------------------------------

    def get_request_status(
        self,
        request_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve current status information for a request."""
        query = """
            SELECT 
                r.request_id,
                r.request_number,
                r.status_id,
                s.status_name
            FROM request r
            JOIN status s ON r.status_id = s.status_id
            WHERE r.request_id = %(request_id)s;
        """
        return self.fetch_one(query, {"request_id": request_id}, conn=conn)

    def get_request_for_status_update(
        self,
        request_id: int,
        conn: psycopg.Connection,
    ) -> dict[str, Any] | None:
        """
        Retrieve request record with exclusive row-level lock (FOR UPDATE).
        Must be executed within an active transaction to guarantee status concurrency safety.
        """
        query = """
            SELECT 
                request_id,
                request_number,
                status_id
            FROM request
            WHERE request_id = %(request_id)s
            FOR UPDATE;
        """
        row = self.fetch_one(query, {"request_id": request_id}, conn=conn)
        if not row:
            return None
        status = self.get_status_by_id(row["status_id"], conn=conn)
        row["status_name"] = status["status_name"] if status else None
        return row

    def get_status_by_id(
        self,
        status_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve status entity by primary key."""
        query = "SELECT status_id, status_name FROM status WHERE status_id = %(status_id)s;"
        return self.fetch_one(query, {"status_id": status_id}, conn=conn)

    def get_status_by_name(
        self,
        status_name: str,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve status entity by status name (case-insensitive)."""
        query = "SELECT status_id, status_name FROM status WHERE LOWER(status_name) = LOWER(%(status_name)s);"
        return self.fetch_one(query, {"status_name": status_name}, conn=conn)

    def list_statuses(
        self,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """List all valid request statuses from the status lookup table."""
        query = "SELECT status_id, status_name FROM status ORDER BY status_id ASC;"
        return self.fetch_all(query, conn=conn)

    def update_request_status(
        self,
        request_id: int,
        status_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """
        Update the status_id on a request.
        Phase 3E status operation updates strictly request.status_id.
        """
        query = """
            UPDATE request
            SET status_id = %(status_id)s
            WHERE request_id = %(request_id)s
            RETURNING request_id, request_number, status_id;
        """
        params = {"request_id": request_id, "status_id": status_id}
        return self.execute_returning(query, params, conn=conn)

    def get_request_for_closure(
        self,
        request_id: int,
        conn: psycopg.Connection,
    ) -> dict[str, Any] | None:
        """
        Retrieve request record with exclusive row-level lock (FOR UPDATE) for closure evaluation.
        Must be executed within an active transaction.
        """
        query = """
            SELECT 
                request_id,
                request_number,
                status_id,
                request_date,
                closed_date,
                resolution_description,
                closed_by
            FROM request
            WHERE request_id = %(request_id)s
            FOR UPDATE;
        """
        row = self.fetch_one(query, {"request_id": request_id}, conn=conn)
        if not row:
            return None
        status = self.get_status_by_id(row["status_id"], conn=conn)
        row["status_name"] = status["status_name"] if status else None
        return row

    def close_request(
        self,
        request_id: int,
        status_id: int,
        closed_date: datetime,
        resolution_description: str,
        closed_by: int,
        conn: psycopg.Connection,
    ) -> dict[str, Any] | None:
        """
        Update request status to Closed and atomically populate all required closure fields.
        Must be executed within an active transaction.
        """
        query = """
            UPDATE request
            SET status_id = %(status_id)s,
                closed_date = %(closed_date)s,
                resolution_description = %(resolution_description)s,
                closed_by = %(closed_by)s
            WHERE request_id = %(request_id)s
            RETURNING request_id, request_number, status_id, closed_date, resolution_description, closed_by;
        """
        params = {
            "request_id": request_id,
            "status_id": status_id,
            "closed_date": closed_date,
            "resolution_description": resolution_description,
            "closed_by": closed_by,
        }
        return self.execute_returning(query, params, conn=conn)

