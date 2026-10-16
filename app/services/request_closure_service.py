"""
Request Closure Service Module
Coordinates the maintenance request closure workflow and status history audit logging.
Validates closure eligibility:
    In Progress -> Closed
    On Hold -> Closed
Enforces closure field completeness, temporal validity, and single-transaction atomicity.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
import psycopg

from app.db import DatabaseManager, get_db_manager
from app.exceptions import (
    AlreadyClosedError,
    DatabaseOperationError,
    InvalidClosureDateError,
    InvalidClosureTransitionError,
    InvalidResolutionDescriptionError,
    RequestNotFoundError,
    StatusNotFoundError,
    UserNotFoundError,
    ValidationError,
)
from app.repositories.request import RequestRepository
from app.utils.logger import get_logger

logger = get_logger(__name__)

STATUS_CLOSED_NAME = "Closed"
CLOSURE_ELIGIBLE_STATUSES = {"In Progress", "On Hold"}


class RequestClosureService:
    """Service layer coordinating maintenance request closure workflows and validation."""

    def __init__(
        self,
        request_repo: RequestRepository | None = None,
        db_manager: DatabaseManager | None = None,
    ) -> None:
        self.request_repo = request_repo or RequestRepository()
        self.db_manager = db_manager or get_db_manager()

    def close_request(
        self,
        request_id: int,
        closed_by: int,
        resolution_description: str,
        closed_date: datetime,
        changed_by: int,
        remarks: str | None = None,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """
        Atomically transition a request to 'Closed' and record closure details and status history.

        Validation rules:
        - request_id exists
        - current status is 'In Progress' or 'On Hold' (rejects 'Open', 'Assigned', 'Closed')
        - closed_by references an existing user (stored in request.closed_by)
        - changed_by references an existing user (stored in status_history.changed_by)
        - no automatic fallback between closed_by and changed_by
        - resolution_description is present, string, non-empty, and non-whitespace
        - closed_date is explicitly provided as a valid datetime
        - closed_date >= request_date

        Atomically updates request (status_id, closed_date, resolution_description, closed_by)
        and inserts exactly one STATUS_HISTORY audit row in a single transaction.
        """
        # 1. Parameter presence and basic type validation
        if request_id is None or not isinstance(request_id, int) or request_id <= 0:
            raise RequestNotFoundError(f"Request with ID {request_id} does not exist")

        if closed_by is None or not isinstance(closed_by, int) or closed_by <= 0:
            raise UserNotFoundError(f"closed_by user ID must be a positive integer: {closed_by}")

        if changed_by is None or not isinstance(changed_by, int) or changed_by <= 0:
            raise UserNotFoundError(f"changed_by user ID must be a positive integer: {changed_by}")

        if resolution_description is None or not isinstance(resolution_description, str) or not resolution_description.strip():
            raise InvalidResolutionDescriptionError("resolution_description must be present and non-empty")

        if closed_date is None or not isinstance(closed_date, datetime):
            raise InvalidClosureDateError("closed_date must be provided as a valid datetime instance")

        # 2. Transaction execution
        try:
            if conn is not None:
                with conn.transaction():
                    return self._execute_close_request(
                        conn=conn,
                        request_id=request_id,
                        closed_by=closed_by,
                        resolution_description=resolution_description.strip(),
                        closed_date=closed_date,
                        changed_by=changed_by,
                        remarks=remarks,
                    )
            else:
                with self.db_manager.transaction() as managed_conn:
                    return self._execute_close_request(
                        conn=managed_conn,
                        request_id=request_id,
                        closed_by=closed_by,
                        resolution_description=resolution_description.strip(),
                        closed_date=closed_date,
                        changed_by=changed_by,
                        remarks=remarks,
                    )
        except (
            RequestNotFoundError,
            UserNotFoundError,
            StatusNotFoundError,
            InvalidClosureTransitionError,
            AlreadyClosedError,
            InvalidResolutionDescriptionError,
            InvalidClosureDateError,
            ValidationError,
        ):
            raise
        except Exception as err:
            logger.error("Failed to execute request closure transaction: %s", err, exc_info=True)
            raise DatabaseOperationError(f"Database error during request closure: {err}") from err

    def _execute_close_request(
        self,
        conn: psycopg.Connection,
        request_id: int,
        closed_by: int,
        resolution_description: str,
        closed_date: datetime,
        changed_by: int,
        remarks: str | None,
    ) -> dict[str, Any]:
        """Internal helper orchestrating closure inside a locked database transaction."""
        # Step A: Lock request row with FOR UPDATE
        req = self.request_repo.get_request_for_closure(request_id, conn=conn)
        if req is None:
            raise RequestNotFoundError(f"Request with ID {request_id} does not exist")

        current_status_name = req["status_name"]
        current_status_id = req["status_id"]
        request_date = req["request_date"]

        # Step B: Validate closure eligibility
        if current_status_name == STATUS_CLOSED_NAME:
            raise AlreadyClosedError(f"Request {request_id} is already Closed")

        if current_status_name not in CLOSURE_ELIGIBLE_STATUSES:
            raise InvalidClosureTransitionError(
                f"Cannot close request {request_id} from status '{current_status_name}'. "
                f"Only requests in {sorted(CLOSURE_ELIGIBLE_STATUSES)} can be closed."
            )

        # Step C: Validate closed_by exists in database
        if not self.request_repo.user_exists(closed_by, conn=conn):
            raise UserNotFoundError(f"User with ID {closed_by} does not exist")

        # Step D: Validate changed_by exists in database
        if not self.request_repo.user_exists(changed_by, conn=conn):
            raise UserNotFoundError(f"User with ID {changed_by} does not exist")

        # Step E: Validate closed_date >= request_date
        if request_date and closed_date < request_date:
            raise InvalidClosureDateError(
                f"closed_date ({closed_date}) cannot precede request_date ({request_date})"
            )

        # Step F: Resolve Closed status ID
        closed_status = self.request_repo.get_status_by_name(STATUS_CLOSED_NAME, conn=conn)
        if not closed_status:
            raise StatusNotFoundError("Status 'Closed' not found in database")
        closed_status_id = closed_status["status_id"]

        # Step G: Update request with closure attributes
        self.request_repo.close_request(
            request_id=request_id,
            status_id=closed_status_id,
            closed_date=closed_date,
            resolution_description=resolution_description,
            closed_by=closed_by,
            conn=conn,
        )

        # Step H: Insert STATUS_HISTORY audit row
        history_record = self.request_repo.create_status_history(
            data={
                "request_id": request_id,
                "status_id": closed_status_id,
                "changed_by": changed_by,
                "changed_date": closed_date,
                "remarks": remarks.strip() if remarks else None,
            },
            conn=conn,
        )

        # Step I: Retrieve hydrated updated request with complete metadata
        hydrated = self.request_repo.get_by_id(request_id, conn=conn)
        if not hydrated:
            raise DatabaseOperationError(f"Failed to fetch updated request ID {request_id}")

        hydrated["status_history_id"] = history_record["status_history_id"]
        hydrated["status_history"] = history_record

        logger.info(
            "Closed request ID=%s (number=%s) authorized by closed_by=%s, recorded by changed_by=%s",
            request_id,
            req["request_number"],
            closed_by,
            changed_by,
        )
        return hydrated
