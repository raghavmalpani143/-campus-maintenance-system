"""
User Repository Module
Handles data-access operations for USER and ROLE entities.
Follows parameterized query patterns and transactional boundaries.
"""

from __future__ import annotations

from typing import Any
import psycopg

from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    """Data access repository for campus user identity and registration."""

    _BASE_SELECT = """
        SELECT 
            u.user_id,
            u.full_name,
            u.email,
            u.phone,
            u.role_id,
            r.role_name,
            r.description AS role_description,
            u.status
        FROM "user" u
        JOIN role r ON u.role_id = r.role_id
    """

    def get_by_id(
        self,
        user_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve a user by primary key."""
        query = f"{self._BASE_SELECT} WHERE u.user_id = %(user_id)s"
        return self.fetch_one(query, {"user_id": user_id}, conn=conn)

    def get_by_email(
        self,
        email: str,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve a user by email (case-insensitive)."""
        query = f"{self._BASE_SELECT} WHERE LOWER(u.email) = LOWER(%(email)s)"
        return self.fetch_one(query, {"email": email.strip()}, conn=conn)

    def is_email_taken(
        self,
        email: str,
        conn: psycopg.Connection | None = None,
    ) -> bool:
        """Check if an email already exists in either the user or technician table."""
        clean = email.strip().lower()
        query = """
            SELECT 1 FROM "user" WHERE LOWER(email) = %(email)s
            UNION
            SELECT 1 FROM technician WHERE LOWER(email) = %(email)s
        """
        row = self.fetch_one(query, {"email": clean}, conn=conn)
        return row is not None

    def get_role_by_name(
        self,
        role_name: str,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve a role record by name (case-insensitive)."""
        query = """
            SELECT role_id, role_name, description
            FROM role
            WHERE LOWER(role_name) = LOWER(%(role_name)s);
        """
        return self.fetch_one(query, {"role_name": role_name.strip()}, conn=conn)

    def list_roles(
        self,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """List all available roles in the system."""
        query = "SELECT role_id, role_name, description FROM role ORDER BY role_id ASC;"
        return self.fetch_all(query, conn=conn)

    def create_user(
        self,
        data: dict[str, Any],
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """Insert a new campus user record."""
        query = """
            INSERT INTO "user" (
                full_name,
                email,
                phone,
                role_id,
                status
            ) VALUES (
                %(full_name)s,
                %(email)s,
                %(phone)s,
                %(role_id)s,
                %(status)s
            )
            RETURNING user_id, full_name, email, phone, role_id, status;
        """
        row = self.execute_returning(query, data, conn=conn)
        if not row:
            raise RuntimeError("Failed to create user record: no row returned")
        return row
