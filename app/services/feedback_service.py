"""
Feedback Service Module
Coordinates customer satisfaction feedback evaluation for closed maintenance requests.
Enforces:
- 1:0..1 relationship between request and feedback
- Eligibility: only requests in 'Closed' status can receive feedback
- Rating constraint: integer between 1 and 5
- Optional comments
- Transactional atomicity and domain exception handling
- Strict zero side-effect boundary (does NOT touch request status or status history)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
import psycopg

from app.db import DatabaseManager, get_db_manager
from app.exceptions import (
    DatabaseOperationError,
    DuplicateFeedbackError,
    FeedbackNotFoundError,
    InvalidDateError,
    InvalidRatingError,
    RequestNotClosedError,
    RequestNotFoundError,
    UserNotFoundError,
    ValidationError,
)
from app.repositories.feedback import FeedbackRepository
from app.utils.logger import get_logger

logger = get_logger(__name__)


class FeedbackService:
    """Service layer managing requester feedback evaluations."""

    def __init__(
        self,
        feedback_repo: FeedbackRepository | None = None,
        db_manager: DatabaseManager | None = None,
    ) -> None:
        self.feedback_repo = feedback_repo or FeedbackRepository()
        self.db_manager = db_manager or get_db_manager()

    def create_feedback(
        self,
        request_id: int,
        user_id: int,
        rating: int,
        comments: str | None = None,
        feedback_date: datetime | None = None,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """
        Record satisfaction feedback for a closed maintenance request.

        Validation rules:
        - request_id exists and is in 'Closed' status
        - user_id exists
        - rating is an integer between 1 and 5
        - comments are optional (string or None)
        - at most one feedback record per request (1:0..1)
        - feedback_date (if supplied) must be a datetime >= request_date and >= closed_date
        - Does NOT change request status or status history

        Transaction flow:
        BEGIN
        -> verify request/user
        -> verify request is Closed
        -> verify no existing feedback
        -> INSERT feedback
        -> COMMIT
        """
        # 1. Parameter type and range validation
        if request_id is None or not isinstance(request_id, int) or request_id <= 0:
            raise RequestNotFoundError(f"Request with ID {request_id} does not exist")

        if user_id is None or not isinstance(user_id, int) or user_id <= 0:
            raise UserNotFoundError(f"user_id must be a positive integer: {user_id}")

        if (
            rating is None
            or isinstance(rating, bool)
            or not isinstance(rating, int)
            or rating < 1
            or rating > 5
        ):
            raise InvalidRatingError(f"Feedback rating must be an integer between 1 and 5, got: {rating}")

        if feedback_date is not None and not isinstance(feedback_date, datetime):
            raise InvalidDateError("feedback_date must be a valid datetime instance")

        clean_comments = comments.strip() if isinstance(comments, str) else None

        # 2. Transaction execution
        try:
            if conn is not None:
                with conn.transaction():
                    return self._execute_create_feedback(
                        conn=conn,
                        request_id=request_id,
                        user_id=user_id,
                        rating=rating,
                        comments=clean_comments,
                        feedback_date=feedback_date,
                    )
            else:
                with self.db_manager.transaction() as managed_conn:
                    return self._execute_create_feedback(
                        conn=managed_conn,
                        request_id=request_id,
                        user_id=user_id,
                        rating=rating,
                        comments=clean_comments,
                        feedback_date=feedback_date,
                    )
        except (
            RequestNotFoundError,
            UserNotFoundError,
            RequestNotClosedError,
            DuplicateFeedbackError,
            InvalidRatingError,
            InvalidDateError,
            ValidationError,
        ):
            raise
        except Exception as err:
            logger.error("Failed to create feedback for request %s: %s", request_id, err, exc_info=True)
            raise DatabaseOperationError(f"Database error during feedback submission: {err}") from err

    def _execute_create_feedback(
        self,
        conn: psycopg.Connection,
        request_id: int,
        user_id: int,
        rating: int,
        comments: str | None,
        feedback_date: datetime | None,
    ) -> dict[str, Any]:
        """Internal helper orchestrating feedback insertion inside an active transaction."""
        # Step A: Verify request exists and inspect status
        req = self.feedback_repo.get_request_for_feedback(request_id, conn=conn)
        if req is None:
            raise RequestNotFoundError(f"Request with ID {request_id} does not exist")

        # Step B: Verify user exists
        if not self.feedback_repo.user_exists(user_id, conn=conn):
            raise UserNotFoundError(f"User with ID {user_id} does not exist")

        # Step C: Verify request is Closed
        if req["status_name"] != "Closed":
            raise RequestNotClosedError(
                f"Feedback can only be submitted for Closed requests. Current status: '{req['status_name']}'"
            )

        # Step D: Verify temporal validity if feedback_date provided
        if feedback_date is not None:
            if req["request_date"] and feedback_date < req["request_date"]:
                raise InvalidDateError(
                    f"Feedback date ({feedback_date}) cannot precede request date ({req['request_date']})"
                )
            if req["closed_date"] and feedback_date < req["closed_date"]:
                raise InvalidDateError(
                    f"Feedback date ({feedback_date}) cannot precede request closure date ({req['closed_date']})"
                )

        # Step E: Verify no existing feedback for this request
        if self.feedback_repo.feedback_exists_for_request(request_id, conn=conn):
            raise DuplicateFeedbackError(f"Feedback already exists for maintenance request ID {request_id}")

        # Step F: Insert feedback record
        created = self.feedback_repo.create_feedback(
            data={
                "request_id": request_id,
                "user_id": user_id,
                "rating": rating,
                "comments": comments,
                "feedback_date": feedback_date,
            },
            conn=conn,
        )

        # Step G: Retrieve hydrated feedback with joined request/user metadata
        hydrated = self.feedback_repo.get_feedback_by_id(created["feedback_id"], conn=conn)
        if not hydrated:
            return created

        logger.info(
            "Created feedback ID=%s for request ID=%s (rating=%s) by user ID=%s",
            hydrated["feedback_id"],
            request_id,
            rating,
            user_id,
        )
        return hydrated

    def get_feedback_for_request(
        self,
        request_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any] | None:
        """
        Retrieve feedback for a maintenance request.
        Raises RequestNotFoundError if request_id does not exist.
        Returns None if request exists but has no feedback yet.
        """
        if request_id is None or not isinstance(request_id, int) or request_id <= 0:
            raise RequestNotFoundError(f"Request with ID {request_id} does not exist")

        if not self.feedback_repo.request_exists(request_id, conn=conn):
            raise RequestNotFoundError(f"Request with ID {request_id} does not exist")

        return self.feedback_repo.get_feedback_by_request_id(request_id, conn=conn)

    def get_feedback_by_id(
        self,
        feedback_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """
        Retrieve a feedback record by primary key.
        Raises FeedbackNotFoundError if feedback_id does not exist.
        """
        if feedback_id is None or not isinstance(feedback_id, int) or feedback_id <= 0:
            raise FeedbackNotFoundError(f"Feedback with ID {feedback_id} does not exist")

        feedback = self.feedback_repo.get_feedback_by_id(feedback_id, conn=conn)
        if not feedback:
            raise FeedbackNotFoundError(f"Feedback with ID {feedback_id} does not exist")
        return feedback
