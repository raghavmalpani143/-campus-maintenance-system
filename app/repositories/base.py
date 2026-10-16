"""
Base Repository Module
Provides generic database query and execution primitives with transaction awareness.
"""

from __future__ import annotations

from typing import Any, Sequence
import psycopg

from app.db import get_connection


class BaseRepository:
    """Base repository handling parameterized queries and connection lifecycle."""

    @staticmethod
    def fetch_one(
        query: str,
        params: Sequence[Any] | dict[str, Any] | None = None,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Execute a read query and return the first row as a dictionary, or None."""
        if conn is not None:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchone()
        else:
            with get_connection() as borrowed_conn:
                with borrowed_conn.cursor() as cur:
                    cur.execute(query, params)
                    return cur.fetchone()

    @staticmethod
    def fetch_all(
        query: str,
        params: Sequence[Any] | dict[str, Any] | None = None,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a read query and return all matching rows as dictionaries."""
        if conn is not None:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()
        else:
            with get_connection() as borrowed_conn:
                with borrowed_conn.cursor() as cur:
                    cur.execute(query, params)
                    return cur.fetchall()

    @staticmethod
    def execute(
        query: str,
        params: Sequence[Any] | dict[str, Any] | None = None,
        conn: psycopg.Connection | None = None,
    ) -> int:
        """Execute a DML command and return the number of affected rows."""
        if conn is not None:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.rowcount
        else:
            with get_connection() as borrowed_conn:
                with borrowed_conn.cursor() as cur:
                    cur.execute(query, params)
                    borrowed_conn.commit()
                    return cur.rowcount

    @staticmethod
    def execute_returning(
        query: str,
        params: Sequence[Any] | dict[str, Any] | None = None,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Execute a DML command with RETURNING clause and return the resulting row as a dict."""
        if conn is not None:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchone()
        else:
            with get_connection() as borrowed_conn:
                with borrowed_conn.cursor() as cur:
                    cur.execute(query, params)
                    row = cur.fetchone()
                    borrowed_conn.commit()
                    return row
