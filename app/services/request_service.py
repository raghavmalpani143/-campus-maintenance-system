"""
Request Service Module
Implements business rules, validation, atomic transactions, and query filtering for maintenance requests.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import psycopg

from app.db import DatabaseManager, get_db_manager
from app.exceptions import (
    AssetNotFoundError,
    CategoryNotFoundError,
    DatabaseOperationError,
    DuplicateRequestNumberError,
    ImmutableFieldError,
    InvalidDateError,
    InvalidDescriptionError,
    InvalidFilterError,
    InvalidRequestDateError,
    InvalidStatusTransitionError,
    NotFoundError,
    PriorityNotFoundError,
    RequesterNotFoundError,
    RequestNotFoundError,
    RoomNotFoundError,
    SameStatusUpdateError,
    StatusNotFoundError,
    UserNotFoundError,
    ValidationError,
)
from app.repositories.request import ALLOWED_UPDATE_FIELDS, RequestRepository
from app.utils.logger import get_logger

logger = get_logger(__name__)

STATUS_OPEN_ID = 1
STATUS_CLOSED_ID = 5

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "Open": {"Assigned"},
    "Assigned": {"In Progress"},
    "In Progress": {"On Hold"},
    "On Hold": {"In Progress"},
    "Closed": set(),
}



class RequestService:
    """Service layer coordinating maintenance request operations and validation."""

    def __init__(
        self,
        request_repo: RequestRepository | None = None,
        db_manager: DatabaseManager | None = None,
    ) -> None:
        self.request_repo = request_repo or RequestRepository()
        self.db_manager = db_manager or get_db_manager()

    # -------------------------------------------------------------------------
    # Request Creation Workflow
    # -------------------------------------------------------------------------

    def create_request(
        self,
        description: str,
        category_id: int,
        priority_id: int,
        requested_by: int,
        room_id: int,
        asset_id: int | None = None,
        request_number: str | None = None,
        request_date: datetime | None = None,
        remarks: str | None = None,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """
        Validate and create a maintenance request within an atomic transaction.
        Synchronously creates initial STATUS_HISTORY row with status 'Open'.
        Rolls back the entire operation if any step fails.
        """
        # 1. Validate description
        if not description or not isinstance(description, str) or not description.strip():
            raise InvalidDescriptionError("Description is required and cannot be blank")
        clean_description = description.strip()

        # 2. Validate request date
        if request_date is None:
            effective_request_date = datetime.now()
        else:
            if not isinstance(request_date, datetime):
                raise InvalidRequestDateError("Request date must be a valid datetime instance")
            now = datetime.now(request_date.tzinfo) if request_date.tzinfo else datetime.now()
            if request_date > now:
                raise InvalidRequestDateError(f"Request date cannot be in the future: {request_date}")
            effective_request_date = request_date

        # 3. Validate existence of related foreign key entities
        if not self.request_repo.user_exists(requested_by, conn=conn):
            raise RequesterNotFoundError(f"Requester with user ID {requested_by} does not exist")

        if not self.request_repo.category_exists(category_id, conn=conn):
            raise CategoryNotFoundError(f"Category with ID {category_id} does not exist")

        if not self.request_repo.priority_exists(priority_id, conn=conn):
            raise PriorityNotFoundError(f"Priority with ID {priority_id} does not exist")

        if not self.request_repo.room_exists(room_id, conn=conn):
            raise RoomNotFoundError(f"Room with ID {room_id} does not exist")

        if asset_id is not None:
            asset = self.request_repo.get_asset(asset_id, conn=conn)
            if not asset:
                raise AssetNotFoundError(f"Asset with ID {asset_id} does not exist")
            if asset["room_id"] != room_id:
                raise ValidationError(
                    f"Asset ID {asset_id} is located in room ID {asset['room_id']}, not the requested room ID {room_id}"
                )

        # 4. Generate or validate unique request number
        date_str = effective_request_date.strftime("%Y%m%d")
        if request_number:
            if not isinstance(request_number, str) or not request_number.strip():
                raise ValidationError("Supplied request_number cannot be blank")
            if len(request_number) > 30:
                raise ValidationError("Request number exceeds maximum length of 30 characters")
            if self.request_repo.exists_by_request_number(request_number, conn=conn):
                raise DuplicateRequestNumberError(f"Request number '{request_number}' already exists")
            final_request_number = request_number.strip()
        else:
            seq = self.request_repo.get_next_sequence_for_date(date_str, conn=conn)
            final_request_number = f"REQ-{date_str}-{seq:04d}"

        # 5. Execute atomic transaction (REQUEST + initial STATUS_HISTORY)
        try:
            if conn is not None:
                # Use caller's existing connection / savepoint
                with conn.transaction():
                    return self._execute_creation_transaction(
                        conn=conn,
                        request_number=final_request_number,
                        request_date=effective_request_date,
                        description=clean_description,
                        category_id=category_id,
                        priority_id=priority_id,
                        requested_by=requested_by,
                        room_id=room_id,
                        asset_id=asset_id,
                        remarks=remarks,
                    )
            else:
                with self.db_manager.transaction() as managed_conn:
                    return self._execute_creation_transaction(
                        conn=managed_conn,
                        request_number=final_request_number,
                        request_date=effective_request_date,
                        description=clean_description,
                        category_id=category_id,
                        priority_id=priority_id,
                        requested_by=requested_by,
                        room_id=room_id,
                        asset_id=asset_id,
                        remarks=remarks,
                    )
        except (ValidationError, NotFoundError):
            raise
        except Exception as err:
            logger.error("Failed to execute request creation transaction: %s", err, exc_info=True)
            raise DatabaseOperationError(f"Database error during request creation: {err}") from err

    def _execute_creation_transaction(
        self,
        conn: psycopg.Connection,
        request_number: str,
        request_date: datetime,
        description: str,
        category_id: int,
        priority_id: int,
        requested_by: int,
        room_id: int,
        asset_id: int | None,
        remarks: str | None,
    ) -> dict[str, Any]:
        """Internal helper executing INSERT statements within an active transaction."""
        # 1. Insert Request with status Open (1)
        created_request = self.request_repo.create_request(
            data={
                "request_number": request_number,
                "request_date": request_date,
                "description": description,
                "category_id": category_id,
                "priority_id": priority_id,
                "requested_by": requested_by,
                "room_id": room_id,
                "asset_id": asset_id,
                "status_id": STATUS_OPEN_ID,
            },
            conn=conn,
        )
        request_id = created_request["request_id"]

        # 2. Insert initial Status History record
        history_remarks = remarks or "Initial request submission (Open)"
        self.request_repo.create_status_history(
            data={
                "request_id": request_id,
                "status_id": STATUS_OPEN_ID,
                "changed_by": requested_by,
                "changed_date": request_date,
                "remarks": history_remarks,
            },
            conn=conn,
        )

        logger.info(
            "Created request ID=%s (%s) with initial status Open and audit log entry",
            request_id,
            request_number,
        )

        # 3. Retrieve and return complete joined entity
        hydrated = self.request_repo.get_by_id(request_id, conn=conn)
        if not hydrated:
            raise DatabaseOperationError(f"Failed to fetch newly created request ID {request_id}")
        return hydrated

    # -------------------------------------------------------------------------
    # Retrieval and Search Queries
    # -------------------------------------------------------------------------

    def get_request_by_id(
        self,
        request_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """Retrieve request by primary key, or raise RequestNotFoundError."""
        req = self.request_repo.get_by_id(request_id, conn=conn)
        if not req:
            raise RequestNotFoundError(f"Request with ID {request_id} does not exist")
        return req

    def get_request_by_number(
        self,
        request_number: str,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """Retrieve request by unique tracking number, or raise RequestNotFoundError."""
        req = self.request_repo.get_by_request_number(request_number, conn=conn)
        if not req:
            raise RequestNotFoundError(f"Request with number '{request_number}' does not exist")
        return req

    def get_status_history(
        self,
        request_id: int,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve audit history trail for a request."""
        # Ensure request exists
        self.get_request_by_id(request_id, conn=conn)
        return self.request_repo.get_status_history_for_request(request_id, conn=conn)

    def list_requests(
        self,
        filters: dict[str, Any] | None = None,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """
        List requests using parameterized filters.
        Validates filter types and bounds.
        """
        filters = filters or {}
        limit = filters.get("limit", 100)
        offset = filters.get("offset", 0)

        if not isinstance(limit, int) or limit < 1:
            raise InvalidFilterError("Limit filter must be a positive integer")
        if not isinstance(offset, int) or offset < 0:
            raise InvalidFilterError("Offset filter must be a non-negative integer")

        return self.request_repo.list_requests(filters=filters, conn=conn)

    # -------------------------------------------------------------------------
    # Permitted Request Updates
    # -------------------------------------------------------------------------

    def update_request(
        self,
        request_id: int,
        updates: dict[str, Any],
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """
        Update explicitly permitted mutable fields on an existing, non-closed request.
        Direct modification of status_id, status_history, closure fields, assignments,
        or costs is strictly prohibited.
        """
        if not updates:
            return self.get_request_by_id(request_id, conn=conn)

        # 1. Enforce field whitelist
        disallowed = set(updates.keys()) - ALLOWED_UPDATE_FIELDS
        if disallowed:
            raise ImmutableFieldError(
                f"Fields {sorted(list(disallowed))} are not permitted to be updated directly on a request"
            )

        # 2. Check request existence and state
        existing = self.get_request_by_id(request_id, conn=conn)
        if existing["status_id"] == STATUS_CLOSED_ID:
            raise ValidationError("Cannot modify attributes of a Closed maintenance request")

        # 3. Validate specific field values if present in updates
        if "description" in updates:
            desc = updates["description"]
            if not desc or not isinstance(desc, str) or not desc.strip():
                raise InvalidDescriptionError("Updated description cannot be blank")
            updates["description"] = desc.strip()

        if "category_id" in updates:
            cat_id = updates["category_id"]
            if not self.request_repo.category_exists(cat_id, conn=conn):
                raise CategoryNotFoundError(f"Category with ID {cat_id} does not exist")

        if "priority_id" in updates:
            prio_id = updates["priority_id"]
            if not self.request_repo.priority_exists(prio_id, conn=conn):
                raise PriorityNotFoundError(f"Priority with ID {prio_id} does not exist")

        target_room_id = updates.get("room_id", existing["room_id"])
        if "room_id" in updates:
            if not self.request_repo.room_exists(target_room_id, conn=conn):
                raise RoomNotFoundError(f"Room with ID {target_room_id} does not exist")

        if "asset_id" in updates:
            target_asset_id = updates["asset_id"]
            if target_asset_id is not None:
                asset = self.request_repo.get_asset(target_asset_id, conn=conn)
                if not asset:
                    raise AssetNotFoundError(f"Asset with ID {target_asset_id} does not exist")
                if asset["room_id"] != target_room_id:
                    raise ValidationError(
                        f"Asset ID {target_asset_id} is in room {asset['room_id']}, not room {target_room_id}"
                    )

        # 4. Perform update via repository
        updated = self.request_repo.update_request(request_id, updates, conn=conn)
        if not updated:
            raise DatabaseOperationError(f"Failed to update request ID {request_id}")

        logger.info("Updated request ID=%s with fields %s", request_id, list(updates.keys()))
        return updated

    # -------------------------------------------------------------------------
    # Request Status Management (Phase 3E)
    # -------------------------------------------------------------------------

    def get_request_status(
        self,
        request_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """
        Retrieve current status information for a request.
        Raises RequestNotFoundError if request_id does not exist.
        """
        if request_id is None or not isinstance(request_id, int) or request_id <= 0:
            raise RequestNotFoundError(f"Request with ID {request_id} does not exist")

        status_info = self.request_repo.get_request_status(request_id, conn=conn)
        if not status_info:
            raise RequestNotFoundError(f"Request with ID {request_id} does not exist")
        return status_info

    def change_request_status(
        self,
        request_id: int,
        new_status: str | int,
        changed_by: int,
        remarks: str | None = None,
        changed_date: datetime | None = None,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """
        Atomically transition a request's status and record the change in status_history.
        Enforces approved operational transition lifecycle:
            Open -> Assigned -> In Progress <-> On Hold
        Uses row-level locking (FOR UPDATE) to prevent concurrency races.
        """
        # 1. Basic parameter validation
        if request_id is None or not isinstance(request_id, int) or request_id <= 0:
            raise RequestNotFoundError(f"Request with ID {request_id} does not exist")

        if new_status is None:
            raise StatusNotFoundError("Target status must not be None")

        if changed_by is None or not isinstance(changed_by, int) or changed_by <= 0:
            raise UserNotFoundError(f"User ID must be a positive integer: {changed_by}")

        if changed_date is not None and not isinstance(changed_date, datetime):
            raise InvalidDateError("changed_date must be a valid datetime instance")

        # 2. Execute atomic transition inside transaction
        try:
            if conn is not None:
                with conn.transaction():
                    return self._execute_change_request_status(
                        conn=conn,
                        request_id=request_id,
                        new_status=new_status,
                        changed_by=changed_by,
                        remarks=remarks,
                        changed_date=changed_date,
                    )
            else:
                with self.db_manager.transaction() as managed_conn:
                    return self._execute_change_request_status(
                        conn=managed_conn,
                        request_id=request_id,
                        new_status=new_status,
                        changed_by=changed_by,
                        remarks=remarks,
                        changed_date=changed_date,
                    )
        except (
            RequestNotFoundError,
            StatusNotFoundError,
            UserNotFoundError,
            InvalidStatusTransitionError,
            SameStatusUpdateError,
            InvalidDateError,
            ValidationError,
        ):
            raise
        except Exception as err:
            logger.error("Failed to execute status change transaction: %s", err, exc_info=True)
            raise DatabaseOperationError(f"Database error during status transition: {err}") from err

    def _execute_change_request_status(
        self,
        conn: psycopg.Connection,
        request_id: int,
        new_status: str | int,
        changed_by: int,
        remarks: str | None,
        changed_date: datetime | None,
    ) -> dict[str, Any]:
        """Internal helper orchestrating the atomic status update and audit trail insertion."""
        # 1. Lock and read request record with FOR UPDATE
        req = self.request_repo.get_request_for_status_update(request_id, conn=conn)
        if req is None:
            raise RequestNotFoundError(f"Request with ID {request_id} does not exist")

        current_status_id = req["status_id"]
        current_status_name = req["status_name"]

        # 2. Resolve target status
        if isinstance(new_status, int):
            target_status = self.request_repo.get_status_by_id(new_status, conn=conn)
        elif isinstance(new_status, str) and new_status.strip():
            target_status = self.request_repo.get_status_by_name(new_status.strip(), conn=conn)
        else:
            raise StatusNotFoundError(f"Invalid status specification: {new_status}")

        if not target_status:
            raise StatusNotFoundError(f"Status '{new_status}' does not exist")

        target_status_id = target_status["status_id"]
        target_status_name = target_status["status_name"]

        # 3. Verify changed_by user exists
        if not self.request_repo.user_exists(changed_by, conn=conn):
            raise UserNotFoundError(f"User with ID {changed_by} does not exist")

        # 4. Check if requested status is the current status
        if target_status_id == current_status_id:
            raise SameStatusUpdateError(
                f"Request {request_id} is already in status '{current_status_name}'"
            )

        # 5. Validate status transition
        allowed = ALLOWED_TRANSITIONS.get(current_status_name, set())
        if target_status_name not in allowed:
            raise InvalidStatusTransitionError(
                f"Invalid status transition from '{current_status_name}' to '{target_status_name}' for request {request_id}"
            )

        # 6. Update request status in database
        self.request_repo.update_request_status(
            request_id=request_id,
            status_id=target_status_id,
            conn=conn,
        )

        # 7. Insert status_history audit record
        eff_changed_date = changed_date if changed_date is not None else datetime.now()
        history_record = self.request_repo.create_status_history(
            data={
                "request_id": request_id,
                "status_id": target_status_id,
                "changed_by": changed_by,
                "changed_date": eff_changed_date,
                "remarks": remarks.strip() if remarks else None,
            },
            conn=conn,
        )

        # 8. Retrieve hydrated updated request with status_history details
        hydrated = self.request_repo.get_by_id(request_id, conn=conn)
        if not hydrated:
            raise DatabaseOperationError(f"Failed to fetch updated request ID {request_id}")

        hydrated["status_history_id"] = history_record["status_history_id"]
        hydrated["status_history"] = history_record

        logger.info(
            "Updated request ID=%s status: '%s' -> '%s' by user ID=%s",
            request_id,
            current_status_name,
            target_status_name,
            changed_by,
        )
        return hydrated

    # -------------------------------------------------------------------------
    # Request Closure Workflow (Phase 3F)
    # -------------------------------------------------------------------------

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
        Delegates to RequestClosureService.
        """
        from app.services.request_closure_service import RequestClosureService

        closure_service = RequestClosureService(self.request_repo, self.db_manager)
        return closure_service.close_request(
            request_id=request_id,
            closed_by=closed_by,
            resolution_description=resolution_description,
            closed_date=closed_date,
            changed_by=changed_by,
            remarks=remarks,
            conn=conn,
        )

    # -------------------------------------------------------------------------
    # Request Feedback (Phase 3G)
    # -------------------------------------------------------------------------

    def create_feedback(
        self,
        request_id: int,
        user_id: int,
        rating: int,
        comments: str | None = None,
        feedback_date: datetime | None = None,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """Record satisfaction feedback for a closed maintenance request. Delegates to FeedbackService."""
        from app.services.feedback_service import FeedbackService

        feedback_service = FeedbackService(db_manager=self.db_manager)
        return feedback_service.create_feedback(
            request_id=request_id,
            user_id=user_id,
            rating=rating,
            comments=comments,
            feedback_date=feedback_date,
            conn=conn,
        )

    def get_feedback_for_request(
        self,
        request_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve feedback for a maintenance request. Delegates to FeedbackService."""
        from app.services.feedback_service import FeedbackService

        feedback_service = FeedbackService(db_manager=self.db_manager)
        return feedback_service.get_feedback_for_request(
            request_id=request_id,
            conn=conn,
        )

