"""
Feedback Repository Module
Handles all parameterized data-access operations for the FEEDBACK entity.
Stores requester satisfaction evaluations upon request closure (1:0..1 cardinality).
"""

from __future__ import annotations

from typing import Any
import psycopg

from app.repositories.base import BaseRepository


class FeedbackRepository(BaseRepository):
    """Data access repository for customer satisfaction evaluations."""

    _BASE_SELECT = """
        SELECT 
            f.feedback_id,
            f.request_id,
            r.request_number,
            f.user_id,
            u.full_name AS user_name,
            f.rating,
            f.comments,
            f.feedback_date
        FROM feedback f
        JOIN request r ON f.request_id = r.request_id
        JOIN "user" u ON f.user_id = u.user_id
    """

    def create_feedback(
        self,
        data: dict[str, Any],
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """
        Insert a new feedback record.
        Enforces 1:0..1 cardinality with request via DB unique constraint uq_feedback_request.
        """
        query = """
            INSERT INTO feedback (
                request_id,
                user_id,
                rating,
                comments,
                feedback_date
            ) VALUES (
                %(request_id)s,
                %(user_id)s,
                %(rating)s,
                %(comments)s,
                COALESCE(%(feedback_date)s, CURRENT_TIMESTAMP)
            )
            RETURNING 
                feedback_id,
                request_id,
                user_id,
                rating,
                comments,
                feedback_date;
        """
        row = self.execute_returning(query, data, conn=conn)
        if not row:
            raise RuntimeError("Failed to insert feedback record: no row returned")
        return row

    def get_feedback_by_id(
        self,
        feedback_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve feedback by primary key with joined request and user metadata."""
        query = f"{self._BASE_SELECT} WHERE f.feedback_id = %(feedback_id)s;"
        return self.fetch_one(query, {"feedback_id": feedback_id}, conn=conn)

    def get_feedback_by_request_id(
        self,
        request_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve feedback for a specific maintenance request (1:0..1 relationship)."""
        query = f"{self._BASE_SELECT} WHERE f.request_id = %(request_id)s;"
        return self.fetch_one(query, {"request_id": request_id}, conn=conn)

    def feedback_exists_for_request(
        self,
        request_id: int,
        conn: psycopg.Connection | None = None,
    ) -> bool:
        """Check whether feedback has already been submitted for a request."""
        query = "SELECT 1 FROM feedback WHERE request_id = %(request_id)s LIMIT 1;"
        res = self.fetch_one(query, {"request_id": request_id}, conn=conn)
        return res is not None

    def get_request_for_feedback(
        self,
        request_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve request details and status for feedback eligibility validation."""
        query = """
            SELECT 
                r.request_id,
                r.request_number,
                r.status_id,
                s.status_name,
                r.request_date,
                r.closed_date,
                r.requested_by
            FROM request r
            JOIN status s ON r.status_id = s.status_id
            WHERE r.request_id = %(request_id)s;
        """
        return self.fetch_one(query, {"request_id": request_id}, conn=conn)

    def user_exists(
        self,
        user_id: int,
        conn: psycopg.Connection | None = None,
    ) -> bool:
        """Check whether a user exists in the database."""
        query = 'SELECT 1 FROM "user" WHERE user_id = %(user_id)s LIMIT 1;'
        res = self.fetch_one(query, {"user_id": user_id}, conn=conn)
        return res is not None

    def request_exists(
        self,
        request_id: int,
        conn: psycopg.Connection | None = None,
    ) -> bool:
        """Check whether a request exists in the database."""
        query = "SELECT 1 FROM request WHERE request_id = %(request_id)s LIMIT 1;"
        res = self.fetch_one(query, {"request_id": request_id}, conn=conn)
        return res is not None

    def list_feedback(
        self,
        filters: dict[str, Any] | None = None,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """List and filter feedback entries."""
        filters = filters or {}
        conditions: list[str] = []
        params: dict[str, Any] = {}

        if filters.get("request_id") is not None:
            conditions.append("f.request_id = %(request_id)s")
            params["request_id"] = filters["request_id"]

        if filters.get("user_id") is not None:
            conditions.append("f.user_id = %(user_id)s")
            params["user_id"] = filters["user_id"]

        if filters.get("rating") is not None:
            conditions.append("f.rating = %(rating)s")
            params["rating"] = filters["rating"]

        where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        limit = filters.get("limit", 100)
        offset = filters.get("offset", 0)
        params["limit"] = limit
        params["offset"] = offset

        query = f"""
            {self._BASE_SELECT}
            {where_clause}
            ORDER BY f.feedback_date DESC, f.feedback_id DESC
            LIMIT %(limit)s OFFSET %(offset)s;
        """
        return self.fetch_all(query, params, conn=conn)
