"""
Work Log Service Module
Coordinates work log creation, retrieval, listing, and updates.
Enforces hours validation, description requirements, and assignment references.
Ensures zero side-effects on inventory, costs, materials, or request status.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, DecimalException
from typing import Any
import psycopg

from app.db import DatabaseManager, get_db_manager
from app.exceptions import (
    AssignmentNotFoundError,
    DatabaseOperationError,
    ImmutableFieldError,
    InvalidDateError,
    InvalidFilterError,
    InvalidHoursSpentError,
    InvalidWorkDescriptionError,
    ValidationError,
    WorkLogNotFoundError,
)
from app.repositories.work_log import ALLOWED_WORK_LOG_UPDATE_FIELDS, WorkLogRepository
from app.utils.logger import get_logger

logger = get_logger(__name__)


class WorkLogService:
    """Service layer managing labor work logs linked to technician assignments."""

    def __init__(
        self,
        work_log_repo: WorkLogRepository | None = None,
        db_manager: DatabaseManager | None = None,
    ) -> None:
        self.work_log_repo = work_log_repo or WorkLogRepository()
        self.db_manager = db_manager or get_db_manager()

    def create_work_log(
        self,
        assignment_id: int,
        work_description: str,
        hours_spent: float | Decimal | int,
        work_date: datetime | None = None,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """
        Record a labor work log against an existing technician assignment.
        Does NOT touch MATERIAL, WORK_LOG_MATERIAL, COST, or REQUEST.status_id.
        """
        # 1. Validate assignment existence
        if not self.work_log_repo.assignment_exists(assignment_id, conn=conn):
            raise AssignmentNotFoundError(f"Assignment with ID {assignment_id} does not exist")

        # 2. Validate work description
        if not work_description or not isinstance(work_description, str) or not work_description.strip():
            raise InvalidWorkDescriptionError("Work description is required and cannot be blank")
        clean_description = work_description.strip()

        # 3. Validate hours spent (non-negative per chk_work_log_hours_spent)
        try:
            numeric_hours = Decimal(str(hours_spent))
        except (ValueError, TypeError, DecimalException) as err:
            raise InvalidHoursSpentError(f"Hours spent must be a numeric value: {hours_spent}") from err

        if numeric_hours < 0:
            raise InvalidHoursSpentError(f"Hours spent cannot be negative: {numeric_hours}")

        # 4. Validate work date (WorkDate <= CURRENT_TIMESTAMP per Data Dictionary)
        effective_work_date = work_date if work_date is not None else datetime.now()
        if not isinstance(effective_work_date, datetime):
            raise InvalidDateError("Work date must be a valid datetime instance")

        now = datetime.now(effective_work_date.tzinfo) if effective_work_date.tzinfo else datetime.now()
        if effective_work_date > now:
            raise InvalidDateError(f"Work date cannot be in the future: {effective_work_date}")

        # 5. Execute creation in transaction
        try:
            if conn is not None:
                with conn.transaction():
                    return self._execute_create(
                        conn=conn,
                        assignment_id=assignment_id,
                        work_date=effective_work_date,
                        work_description=clean_description,
                        hours_spent=numeric_hours,
                    )
            else:
                with self.db_manager.transaction() as managed_conn:
                    return self._execute_create(
                        conn=managed_conn,
                        assignment_id=assignment_id,
                        work_date=effective_work_date,
                        work_description=clean_description,
                        hours_spent=numeric_hours,
                    )
        except (ValidationError, AssignmentNotFoundError):
            raise
        except Exception as err:
            logger.error("Failed to execute work log creation: %s", err, exc_info=True)
            raise DatabaseOperationError(f"Database error during work log creation: {err}") from err

    def _execute_create(
        self,
        conn: psycopg.Connection,
        assignment_id: int,
        work_date: datetime,
        work_description: str,
        hours_spent: Decimal,
    ) -> dict[str, Any]:
        """Internal helper executing insert and returning joined entity."""
        created = self.work_log_repo.create_work_log(
            data={
                "assignment_id": assignment_id,
                "work_date": work_date,
                "work_description": work_description,
                "hours_spent": hours_spent,
            },
            conn=conn,
        )
        work_log_id = created["work_log_id"]
        hydrated = self.work_log_repo.get_by_id(work_log_id, conn=conn)
        if not hydrated:
            raise DatabaseOperationError(f"Failed to fetch newly created work log ID {work_log_id}")
        logger.info(
            "Created work log ID=%s (Assignment ID=%s, Hours=%s)",
            work_log_id,
            assignment_id,
            hours_spent,
        )
        return hydrated

    def get_work_log_by_id(
        self,
        work_log_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """Retrieve work log by ID or raise WorkLogNotFoundError."""
        work_log = self.work_log_repo.get_by_id(work_log_id, conn=conn)
        if not work_log:
            raise WorkLogNotFoundError(f"Work log with ID {work_log_id} does not exist")
        return work_log

    def list_work_logs(
        self,
        filters: dict[str, Any] | None = None,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """List work logs with validated filters."""
        filters = filters or {}
        limit = filters.get("limit", 100)
        offset = filters.get("offset", 0)

        if not isinstance(limit, int) or limit < 1:
            raise InvalidFilterError("Limit filter must be a positive integer")
        if not isinstance(offset, int) or offset < 0:
            raise InvalidFilterError("Offset filter must be a non-negative integer")

        return self.work_log_repo.list_work_logs(filters=filters, conn=conn)

    def update_work_log(
        self,
        work_log_id: int,
        updates: dict[str, Any],
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """
        Update explicitly permitted mutable fields on a work log.
        Updating work_log_id or assignment_id is strictly disallowed.
        """
        if not updates:
            return self.get_work_log_by_id(work_log_id, conn=conn)

        # 1. Enforce field whitelist
        disallowed = set(updates.keys()) - ALLOWED_WORK_LOG_UPDATE_FIELDS
        if disallowed:
            raise ImmutableFieldError(
                f"Fields {sorted(list(disallowed))} are not permitted to be updated directly on a work log"
            )

        # 2. Check work log existence
        self.get_work_log_by_id(work_log_id, conn=conn)

        # 3. Validate updated values
        if "work_description" in updates:
            desc = updates["work_description"]
            if not desc or not isinstance(desc, str) or not desc.strip():
                raise InvalidWorkDescriptionError("Updated work description cannot be blank")
            updates["work_description"] = desc.strip()

        if "hours_spent" in updates:
            try:
                numeric_hours = Decimal(str(updates["hours_spent"]))
            except (ValueError, TypeError, DecimalException) as err:
                raise InvalidHoursSpentError(f"Updated hours must be a numeric value: {updates['hours_spent']}") from err
            if numeric_hours < 0:
                raise InvalidHoursSpentError(f"Updated hours cannot be negative: {numeric_hours}")
            updates["hours_spent"] = numeric_hours

        if "work_date" in updates:
            w_date = updates["work_date"]
            if not isinstance(w_date, datetime):
                raise InvalidDateError("Updated work date must be a valid datetime instance")
            now = datetime.now(w_date.tzinfo) if w_date.tzinfo else datetime.now()
            if w_date > now:
                raise InvalidDateError(f"Updated work date cannot be in the future: {w_date}")

        # 4. Perform update
        updated = self.work_log_repo.update_work_log(work_log_id, updates, conn=conn)
        if not updated:
            raise DatabaseOperationError(f"Failed to update work log ID {work_log_id}")

        logger.info("Updated work log ID=%s with fields %s", work_log_id, list(updates.keys()))
        return updated
