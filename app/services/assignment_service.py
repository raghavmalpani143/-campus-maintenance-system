"""
Assignment Service Module
Coordinates technician assignment creation, retrieval, listing, and updates.
Validates business invariants and ensures request state is untouched.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
import psycopg

from app.db import DatabaseManager, get_db_manager
from app.exceptions import (
    AssignmentNotFoundError,
    DatabaseOperationError,
    ImmutableFieldError,
    InvalidAssignmentStatusError,
    InvalidDateError,
    InvalidFilterError,
    RequestNotFoundError,
    TechnicianNotFoundError,
    UserNotFoundError,
    ValidationError,
)
from app.repositories.assignment import ALLOWED_ASSIGNMENT_UPDATE_FIELDS, AssignmentRepository
from app.utils.logger import get_logger

logger = get_logger(__name__)

ALLOWED_ASSIGNMENT_STATUSES = frozenset({
    "Assigned",
    "In Progress",
    "Completed",
    "Reassigned",
    "Cancelled",
})


class AssignmentService:
    """Service layer managing technician assignments to maintenance requests."""

    def __init__(
        self,
        assignment_repo: AssignmentRepository | None = None,
        db_manager: DatabaseManager | None = None,
    ) -> None:
        self.assignment_repo = assignment_repo or AssignmentRepository()
        self.db_manager = db_manager or get_db_manager()

    def create_assignment(
        self,
        request_id: int,
        technician_id: int,
        assigned_date: datetime | None = None,
        due_date: datetime | None = None,
        status: str = "Assigned",
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """
        Create a technician assignment for an existing maintenance request.
        Does NOT alter REQUEST.status_id or insert STATUS_HISTORY rows.
        """
        # 1. Validate request and technician existence
        if not self.assignment_repo.request_exists(request_id, conn=conn):
            raise RequestNotFoundError(f"Maintenance request with ID {request_id} does not exist")

        if not self.assignment_repo.technician_exists(technician_id, conn=conn):
            raise TechnicianNotFoundError(f"Technician with ID {technician_id} does not exist")

        # 2. Validate assignment status
        if status not in ALLOWED_ASSIGNMENT_STATUSES:
            raise InvalidAssignmentStatusError(
                f"Invalid assignment status '{status}'. Must be one of: {sorted(list(ALLOWED_ASSIGNMENT_STATUSES))}"
            )

        # 3. Validate assignment dates
        effective_assigned_date = assigned_date if assigned_date is not None else datetime.now()
        if not isinstance(effective_assigned_date, datetime):
            raise InvalidDateError("Assigned date must be a valid datetime instance")

        if due_date is not None:
            if not isinstance(due_date, datetime):
                raise InvalidDateError("Due date must be a valid datetime instance")
            if due_date < effective_assigned_date:
                raise InvalidDateError(
                    f"Due date ({due_date}) cannot precede assigned date ({effective_assigned_date})"
                )

        # 4. Execute creation in transaction
        try:
            if conn is not None:
                with conn.transaction():
                    return self._execute_create(
                        conn=conn,
                        request_id=request_id,
                        technician_id=technician_id,
                        assigned_date=effective_assigned_date,
                        due_date=due_date,
                        status=status,
                    )
            else:
                with self.db_manager.transaction() as managed_conn:
                    return self._execute_create(
                        conn=managed_conn,
                        request_id=request_id,
                        technician_id=technician_id,
                        assigned_date=effective_assigned_date,
                        due_date=due_date,
                        status=status,
                    )
        except (ValidationError, RequestNotFoundError, TechnicianNotFoundError):
            raise
        except Exception as err:
            logger.error("Failed to execute assignment creation: %s", err, exc_info=True)
            raise DatabaseOperationError(f"Database error during assignment creation: {err}") from err

    def _execute_create(
        self,
        conn: psycopg.Connection,
        request_id: int,
        technician_id: int,
        assigned_date: datetime,
        due_date: datetime | None,
        status: str,
    ) -> dict[str, Any]:
        """Internal helper executing insert and returning joined entity."""
        created = self.assignment_repo.create_assignment(
            data={
                "request_id": request_id,
                "technician_id": technician_id,
                "assigned_date": assigned_date,
                "due_date": due_date,
                "status": status,
            },
            conn=conn,
        )
        assignment_id = created["assignment_id"]
        hydrated = self.assignment_repo.get_by_id(assignment_id, conn=conn)
        if not hydrated:
            raise DatabaseOperationError(f"Failed to fetch newly created assignment ID {assignment_id}")
        logger.info(
            "Created assignment ID=%s (Request ID=%s, Tech ID=%s, Status=%s)",
            assignment_id,
            request_id,
            technician_id,
            status,
        )
        return hydrated

    def get_assignment_by_id(
        self,
        assignment_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """Retrieve assignment by ID or raise AssignmentNotFoundError."""
        assignment = self.assignment_repo.get_by_id(assignment_id, conn=conn)
        if not assignment:
            raise AssignmentNotFoundError(f"Assignment with ID {assignment_id} does not exist")
        return assignment

    def list_assignments(
        self,
        filters: dict[str, Any] | None = None,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """List assignments with validated filters."""
        filters = filters or {}
        limit = filters.get("limit", 100)
        offset = filters.get("offset", 0)

        if not isinstance(limit, int) or limit < 1:
            raise InvalidFilterError("Limit filter must be a positive integer")
        if not isinstance(offset, int) or offset < 0:
            raise InvalidFilterError("Offset filter must be a non-negative integer")

        if "status" in filters and filters["status"] not in ALLOWED_ASSIGNMENT_STATUSES:
            raise InvalidAssignmentStatusError(f"Invalid filter status '{filters['status']}'")

        return self.assignment_repo.list_assignments(filters=filters, conn=conn)

    def complete_assignment(
        self,
        assignment_id: int,
        technician_id: int | None = None,
        closed_by: int | None = None,
        resolution_description: str | None = None,
        due_date: datetime | None = None,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """
        Atomically mark assignment as Completed and propagate completion to request lifecycle.
        If all assignments for the request are completed, transitions the request to 'Closed',
        recording closure details and status history in a single database transaction.
        """
        existing = self.get_assignment_by_id(assignment_id, conn=conn)
        if technician_id is not None and int(existing["technician_id"]) != int(technician_id):
            raise ValidationError(
                f"Technician ID {technician_id} is not permitted to modify assignment ID {assignment_id} "
                f"belonging to technician ID {existing['technician_id']}"
            )

        if conn is not None:
            with conn.transaction():
                return self._execute_complete_assignment(
                    conn=conn,
                    assignment_id=assignment_id,
                    existing=existing,
                    due_date=due_date,
                    closed_by=closed_by,
                    resolution_description=resolution_description,
                )
        else:
            with self.db_manager.transaction() as managed_conn:
                return self._execute_complete_assignment(
                    conn=managed_conn,
                    assignment_id=assignment_id,
                    existing=existing,
                    due_date=due_date,
                    closed_by=closed_by,
                    resolution_description=resolution_description,
                )

    def _resolve_closed_by(self, closed_by: int | None, conn: psycopg.Connection) -> int:
        """
        Resolve administrative actor for request closure under the 17-table schema.
        request.closed_by strictly REFERENCES "user"(user_id).
        Technicians belong to the separate technician table without user_id rows.
        If a valid closed_by user ID is provided, validates existence or raises UserNotFoundError.
        Otherwise, dynamically queries the active Facility Manager from the user table.
        """
        if closed_by is not None:
            if not isinstance(closed_by, int) or closed_by <= 0:
                raise UserNotFoundError(f"closed_by user ID must be a positive integer: {closed_by}")
            with conn.cursor() as cur:
                cur.execute('SELECT user_id FROM "user" WHERE user_id = %(uid)s;', {"uid": closed_by})
                row = cur.fetchone()
                if not row:
                    raise UserNotFoundError(f"User with ID {closed_by} does not exist")
                return row["user_id"]

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.user_id
                FROM "user" u
                JOIN role r ON u.role_id = r.role_id
                WHERE r.role_name = 'Facility Manager' AND u.status = 'Active'
                ORDER BY u.user_id ASC
                LIMIT 1;
                """
            )
            mgr = cur.fetchone()
            if mgr:
                return mgr["user_id"]

            cur.execute('SELECT user_id FROM "user" WHERE status = \'Active\' ORDER BY user_id ASC LIMIT 1;')
            fallback = cur.fetchone()
            if fallback:
                return fallback["user_id"]

        return 7

    def _execute_complete_assignment(
        self,
        conn: psycopg.Connection,
        assignment_id: int,
        existing: dict[str, Any],
        due_date: datetime | None = None,
        closed_by: int | None = None,
        resolution_description: str | None = None,
    ) -> dict[str, Any]:
        """Internal helper executing the atomic assignment completion and request closure sequence."""
        # 1. Update assignment status to 'Completed'
        assign_updates: dict[str, Any] = {"status": "Completed"}
        if due_date is not None:
            assign_updates["due_date"] = due_date
        self.assignment_repo.update_assignment(assignment_id, assign_updates, conn=conn)

        # 2. Lock and inspect parent request
        request_id = existing["request_id"]
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT r.request_id, r.status_id, s.status_name, r.request_date
                FROM request r
                JOIN status s ON r.status_id = s.status_id
                WHERE r.request_id = %(req_id)s
                FOR UPDATE;
                """,
                {"req_id": request_id},
            )
            req_row = cur.fetchone()

        if not req_row:
            raise RequestNotFoundError(f"Request with ID {request_id} does not exist")

        # 3. Check for any remaining active assignments on this request
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS active_count
                FROM assignment
                WHERE request_id = %(req_id)s
                  AND assignment_id != %(aid)s
                  AND status IN ('Assigned', 'In Progress');
                """,
                {"req_id": request_id, "aid": assignment_id},
            )
            active_count = cur.fetchone()["active_count"]

        # 4. If all assignments for this request are completed, close the request
        tech_name = existing.get("technician_name") or f"Technician #{existing.get('technician_id')}"
        now = datetime.now()
        effective_closed_by = self._resolve_closed_by(closed_by, conn=conn)
        effective_res_desc = (
            resolution_description.strip()
            if resolution_description and resolution_description.strip()
            else f"Assignment #{assignment_id} completed by technician {tech_name}."
        )

        if active_count == 0:
            if req_row["status_id"] != 5:  # Not already Closed
                with conn.cursor() as cur:
                    # Enforce sequential lifecycle audit history
                    if req_row["status_id"] == 1:  # Open -> Assigned -> In Progress -> Closed
                        cur.execute(
                            """
                            INSERT INTO status_history (request_id, status_id, changed_by, changed_date, remarks)
                            VALUES (%(rid)s, 2, %(cb)s, %(dt)s, %(rem)s);
                            """,
                            {"rid": request_id, "cb": effective_closed_by, "dt": now, "rem": f"Dispatched {tech_name}"},
                        )
                        cur.execute(
                            """
                            INSERT INTO status_history (request_id, status_id, changed_by, changed_date, remarks)
                            VALUES (%(rid)s, 3, %(cb)s, %(dt)s, %(rem)s);
                            """,
                            {"rid": request_id, "cb": effective_closed_by, "dt": now, "rem": "Work commenced"},
                        )
                    elif req_row["status_id"] == 2:  # Assigned -> In Progress -> Closed
                        cur.execute(
                            """
                            INSERT INTO status_history (request_id, status_id, changed_by, changed_date, remarks)
                            VALUES (%(rid)s, 3, %(cb)s, %(dt)s, %(rem)s);
                            """,
                            {"rid": request_id, "cb": effective_closed_by, "dt": now, "rem": f"Work commenced by {tech_name}"},
                        )

                    # Atomically update request with all required closure fields
                    cur.execute(
                        """
                        UPDATE request
                        SET status_id = 5,
                            closed_date = %(closed_date)s,
                            resolution_description = %(resolution_description)s,
                            closed_by = %(closed_by)s
                        WHERE request_id = %(request_id)s;
                        """,
                        {
                            "closed_date": now,
                            "resolution_description": effective_res_desc,
                            "closed_by": effective_closed_by,
                            "request_id": request_id,
                        },
                    )

                    # Insert immutable status history closure audit row
                    cur.execute(
                        """
                        INSERT INTO status_history (request_id, status_id, changed_by, changed_date, remarks)
                        VALUES (%(request_id)s, 5, %(changed_by)s, %(changed_date)s, %(remarks)s);
                        """,
                        {
                            "request_id": request_id,
                            "changed_by": effective_closed_by,
                            "changed_date": now,
                            "remarks": f"Assignment #{assignment_id} marked Completed by technician {tech_name}",
                        },
                    )
        else:
            # Other assignments remain active; advance request to In Progress if it was Assigned
            if req_row["status_id"] == 2:
                with conn.cursor() as cur:
                    cur.execute("UPDATE request SET status_id = 3 WHERE request_id = %(rid)s;", {"rid": request_id})
                    cur.execute(
                        """
                        INSERT INTO status_history (request_id, status_id, changed_by, changed_date, remarks)
                        VALUES (%(rid)s, 3, %(cb)s, %(dt)s, %(rem)s);
                        """,
                        {
                            "rid": request_id,
                            "cb": effective_closed_by,
                            "dt": now,
                            "rem": "Assignment completed, work continues on secondary assignments",
                        },
                    )

        hydrated = self.assignment_repo.get_by_id(assignment_id, conn=conn)
        if not hydrated:
            raise DatabaseOperationError(f"Failed to fetch updated assignment ID {assignment_id}")

        logger.info(
            "Atomically completed assignment ID=%s (Request ID=%s, Tech=%s, RequestStatus=%s)",
            assignment_id,
            request_id,
            tech_name,
            hydrated.get("request_status_name"),
        )
        return hydrated

    def update_assignment(
        self,
        assignment_id: int,
        updates: dict[str, Any],
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """
        Update explicitly permitted mutable fields on an assignment.
        Updating assignment_id or request_id is strictly disallowed.
        If status is updated to 'Completed', atomically executes completion propagation.
        """
        if not updates:
            return self.get_assignment_by_id(assignment_id, conn=conn)

        updates_copy = dict(updates)
        closed_by = updates_copy.pop("closed_by", None)
        resolution_description = updates_copy.pop("resolution_description", None)

        # 1. Enforce field whitelist
        disallowed = set(updates_copy.keys()) - ALLOWED_ASSIGNMENT_UPDATE_FIELDS
        if disallowed:
            raise ImmutableFieldError(
                f"Fields {sorted(list(disallowed))} are not permitted to be updated directly on an assignment"
            )

        # 2. Check assignment existence
        existing = self.get_assignment_by_id(assignment_id, conn=conn)

        # 3. Validate updated values
        if "status" in updates_copy:
            new_status = updates_copy["status"]
            if new_status not in ALLOWED_ASSIGNMENT_STATUSES:
                raise InvalidAssignmentStatusError(f"Invalid assignment status '{new_status}'")

        if "due_date" in updates_copy:
            new_due_date = updates_copy["due_date"]
            if new_due_date is not None:
                if not isinstance(new_due_date, datetime):
                    raise InvalidDateError("Due date must be a valid datetime instance")
                if new_due_date < existing["assigned_date"]:
                    raise InvalidDateError(
                        f"Updated due date ({new_due_date}) cannot precede assigned date ({existing['assigned_date']})"
                    )

        # 4. Perform update: if status is 'Completed', execute atomic completion workflow
        if updates_copy.get("status") == "Completed":
            if conn is not None:
                with conn.transaction():
                    return self._execute_complete_assignment(
                        conn=conn,
                        assignment_id=assignment_id,
                        existing=existing,
                        due_date=updates_copy.get("due_date"),
                        closed_by=closed_by,
                        resolution_description=resolution_description,
                    )
            else:
                with self.db_manager.transaction() as managed_conn:
                    return self._execute_complete_assignment(
                        conn=managed_conn,
                        assignment_id=assignment_id,
                        existing=existing,
                        due_date=updates_copy.get("due_date"),
                        closed_by=closed_by,
                        resolution_description=resolution_description,
                    )

        updated = self.assignment_repo.update_assignment(assignment_id, updates_copy, conn=conn)
        if not updated:
            raise DatabaseOperationError(f"Failed to update assignment ID {assignment_id}")

        logger.info("Updated assignment ID=%s with fields %s", assignment_id, list(updates_copy.keys()))
        return updated
