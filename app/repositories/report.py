"""
Report Repository Module
Provides parameterized read-only data access for the six locked Phase 2 PostgreSQL views:
1. vw_pending_requests
2. vw_request_ageing
3. vw_technician_workload
4. vw_building_maintenance_cost
5. vw_material_usage
6. vw_feedback_summary
"""

from __future__ import annotations

from typing import Any
import psycopg

from app.repositories.base import BaseRepository


class ReportRepository(BaseRepository):
    """Read-only access to authoritative Phase 2 database views."""

    def get_pending_requests(
        self,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve active, unclosed requests from vw_pending_requests."""
        query = "SELECT * FROM vw_pending_requests ORDER BY days_open DESC;"
        return self.fetch_all(query, conn=conn)

    def get_request_ageing(
        self,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve SLA compliance and duration breakdown from vw_request_ageing."""
        query = "SELECT * FROM vw_request_ageing ORDER BY hours_open DESC;"
        return self.fetch_all(query, conn=conn)

    def get_technician_workload(
        self,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve technician allocation and labor summary from vw_technician_workload."""
        query = "SELECT * FROM vw_technician_workload ORDER BY active_assignments DESC, total_assignments DESC;"
        return self.fetch_all(query, conn=conn)

    def get_building_maintenance_cost(
        self,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve expense aggregations by building from vw_building_maintenance_cost."""
        query = "SELECT * FROM vw_building_maintenance_cost ORDER BY total_maintenance_expenditure DESC;"
        return self.fetch_all(query, conn=conn)

    def get_material_usage(
        self,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve inventory consumption analytics from vw_material_usage."""
        query = "SELECT * FROM vw_material_usage ORDER BY total_material_cost DESC;"
        return self.fetch_all(query, conn=conn)

    def get_feedback_summary(
        self,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve quality assurance ratings from vw_feedback_summary."""
        query = "SELECT * FROM vw_feedback_summary ORDER BY average_rating DESC;"
        return self.fetch_all(query, conn=conn)

    def get_lookup_data(
        self,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """Retrieve reference metadata for frontend modal forms."""
        categories = self.fetch_all("SELECT category_id, category_name FROM category ORDER BY category_name;", conn=conn)
        priorities = self.fetch_all("SELECT priority_id, priority_level, response_time_hr FROM priority ORDER BY priority_id;", conn=conn)
        rooms = self.fetch_all("""
            SELECT r.room_id, r.room_number, r.floor, b.building_name 
            FROM room r 
            JOIN building b ON r.building_id = b.building_id 
            ORDER BY b.building_name, r.room_number;
        """, conn=conn)
        users = self.fetch_all("SELECT user_id, full_name, email, role_id FROM \"user\" WHERE status = 'Active' ORDER BY full_name;", conn=conn)
        technicians = self.fetch_all("SELECT technician_id, full_name, department, status, labor_rate FROM technician ORDER BY full_name;", conn=conn)
        assets = self.fetch_all("SELECT asset_id, asset_name, room_id, status FROM asset ORDER BY asset_name;", conn=conn)
        statuses = self.fetch_all("SELECT status_id, status_name FROM status ORDER BY status_id;", conn=conn)
        materials = self.fetch_all("SELECT material_id, material_name, unit, unit_cost, stock_qty FROM material ORDER BY material_name;", conn=conn)

        return {
            "categories": categories,
            "priorities": priorities,
            "rooms": rooms,
            "users": users,
            "technicians": technicians,
            "assets": assets,
            "statuses": statuses,
            "materials": materials,
        }
