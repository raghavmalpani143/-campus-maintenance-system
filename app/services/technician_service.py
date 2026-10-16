"""
Technician Service Module
Coordinates technician profile retrieval, department-to-category mapping,
and incoming unassigned request retrieval for operational technician portals.
"""

from __future__ import annotations

from typing import Any
import psycopg

from app.db import DatabaseManager, get_db_manager
from app.exceptions import NotFoundError
from app.repositories.technician import TechnicianRepository
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Explicit application-level mapping between TECHNICIAN.department and CATEGORY.category_name
DEPARTMENT_TO_CATEGORY_MAP: dict[str, str] = {
    "electrical maintenance": "Electrical",
    "electrical": "Electrical",
    "plumbing & hydraulics": "Plumbing",
    "plumbing": "Plumbing",
    "hvac & refrigeration": "HVAC",
    "hvac": "HVAC",
    "civil & carpentry": "Carpentry & Civil",
    "carpentry & civil": "Carpentry & Civil",
    "carpentry": "Carpentry & Civil",
    "network infrastructure": "Network & IT Infrastructure",
    "network & it infrastructure": "Network & IT Infrastructure",
    "network": "Network & IT Infrastructure",
    "laboratory utilities": "Laboratory Utilities",
    "laboratory utilities maintenance": "Laboratory Utilities",
}


class TechnicianService:
    """Service layer managing technician operations, accounts, and incoming request scoping."""

    def __init__(
        self,
        technician_repo: TechnicianRepository | None = None,
        db_manager: DatabaseManager | None = None,
    ) -> None:
        self.technician_repo = technician_repo or TechnicianRepository()
        self.db_manager = db_manager or get_db_manager()

    @staticmethod
    def map_department_to_category(department: str | None) -> str:
        """
        Map a technician's department name to its corresponding maintenance category name.
        Uses explicit mapping table with sensible partial-match fallback.
        """
        if not department:
            return ""
        clean = department.strip().lower()
        if clean in DEPARTMENT_TO_CATEGORY_MAP:
            return DEPARTMENT_TO_CATEGORY_MAP[clean]

        for key, category in DEPARTMENT_TO_CATEGORY_MAP.items():
            if key in clean or clean in key:
                return category

        return department.strip()

    def get_technician_by_id(
        self,
        technician_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """Retrieve technician by ID or raise NotFoundError."""
        tech = self.technician_repo.get_by_id(technician_id, conn=conn)
        if not tech:
            raise NotFoundError(f"Technician ID {technician_id} not found")
        return tech

    def list_active_technicians(
        self,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """Return all active technicians from PostgreSQL."""
        return self.technician_repo.list_active(conn=conn)

    def get_incoming_requests_for_technician(
        self,
        technician_id: int,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve unassigned, active incoming requests belonging strictly to
        the technician's department/category domain.
        """
        tech = self.get_technician_by_id(technician_id, conn=conn)
        category_name = self.map_department_to_category(tech.get("department"))
        if not category_name:
            return []

        return self.technician_repo.get_incoming_unassigned_requests_by_category(
            category_name=category_name,
            conn=conn,
        )
