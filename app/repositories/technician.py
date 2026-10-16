"""
Technician Repository Module
Handles data-access operations for TECHNICIAN entities and incoming unassigned request queries.
Strictly encapsulates SQL logic and category-filtered work order retrieval.
"""

from __future__ import annotations

from typing import Any
import psycopg

from app.repositories.base import BaseRepository


class TechnicianRepository(BaseRepository):
    """Data access repository for technicians and incoming category-scoped requests."""

    _TECHNICIAN_SELECT = """
        SELECT 
            technician_id,
            full_name,
            phone,
            email,
            department,
            status,
            labor_rate
        FROM technician
    """

    def get_by_id(
        self,
        technician_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve a technician record by primary key."""
        query = f"{self._TECHNICIAN_SELECT} WHERE technician_id = %(tid)s"
        return self.fetch_one(query, {"tid": technician_id}, conn=conn)

    def get_by_email(
        self,
        email: str,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve a technician record by email (case-insensitive)."""
        query = f"{self._TECHNICIAN_SELECT} WHERE LOWER(email) = LOWER(%(email)s)"
        return self.fetch_one(query, {"email": email.strip()}, conn=conn)

    def list_active(
        self,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve all active technician records ordered by technician_id."""
        query = f"{self._TECHNICIAN_SELECT} WHERE status = 'Active' ORDER BY technician_id ASC"
        return self.fetch_all(query, conn=conn)

    def get_incoming_unassigned_requests_by_category(
        self,
        category_name: str,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve active, unassigned maintenance requests belonging to the specified category.
        A request is incoming/unassigned if:
        1. It matches the category name.
        2. Its current status is not Closed (typically 'Open').
        3. No active or completed assignment exists for this request.
        """
        query = """
            SELECT 
                r.request_id,
                r.request_number,
                r.request_date,
                r.description,
                r.category_id,
                c.category_name,
                r.priority_id,
                p.priority_level,
                p.response_time_hr,
                r.requested_by,
                u.full_name AS requester_name,
                u.email AS requester_email,
                r.room_id,
                rm.room_number,
                rm.room_type,
                b.building_id,
                b.building_name,
                r.asset_id,
                a.asset_name,
                a.asset_type,
                r.status_id,
                s.status_name,
                NULL AS assignment_id
            FROM request r
            JOIN category c ON r.category_id = c.category_id
            JOIN priority p ON r.priority_id = p.priority_id
            JOIN "user" u ON r.requested_by = u.user_id
            JOIN room rm ON r.room_id = rm.room_id
            JOIN building b ON rm.building_id = b.building_id
            JOIN status s ON r.status_id = s.status_id
            LEFT JOIN asset a ON r.asset_id = a.asset_id
            WHERE LOWER(c.category_name) = LOWER(%(category_name)s)
              AND s.status_name <> 'Closed'
              AND NOT EXISTS (
                  SELECT 1 FROM assignment a_sub
                  WHERE a_sub.request_id = r.request_id
                    AND a_sub.status IN ('Assigned', 'In Progress', 'Completed')
              )
            ORDER BY r.request_id DESC;
        """
        return self.fetch_all(query, {"category_name": category_name.strip()}, conn=conn)
