"""
Application Domain Exceptions Module
Defines explicit, structured error classes for validation, lookup, and database handling.
"""

from __future__ import annotations


class AppError(Exception):
    """Base exception for all application errors."""
    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


# -----------------------------------------------------------------------------
# Entity Not Found Exceptions
# -----------------------------------------------------------------------------

class NotFoundError(AppError):
    """Base exception when an entity or resource is not found."""
    pass


class RequestNotFoundError(NotFoundError):
    """Raised when a maintenance request is not found by ID or request number."""
    pass


class RequesterNotFoundError(NotFoundError):
    """Raised when the requesting user is not found in the database."""
    pass


class CategoryNotFoundError(NotFoundError):
    """Raised when the specified category ID does not exist."""
    pass


class PriorityNotFoundError(NotFoundError):
    """Raised when the specified priority ID does not exist."""
    pass


class RoomNotFoundError(NotFoundError):
    """Raised when the specified room ID does not exist."""
    pass


class AssetNotFoundError(NotFoundError):
    """Raised when the specified asset ID does not exist."""
    pass


class TechnicianNotFoundError(NotFoundError):
    """Raised when the specified technician ID does not exist."""
    pass


class AssignmentNotFoundError(NotFoundError):
    """Raised when a technician assignment is not found by ID."""
    pass


class WorkLogNotFoundError(NotFoundError):
    """Raised when a work log record is not found by ID."""
    pass


class MaterialNotFoundError(NotFoundError):
    """Raised when a material item is not found by ID."""
    pass


class CostNotFoundError(NotFoundError):
    """Raised when a financial cost record is not found by ID."""
    pass


class StatusNotFoundError(NotFoundError):
    """Raised when the specified status ID or status name does not exist."""
    pass


class UserNotFoundError(NotFoundError):
    """Raised when a specified user ID does not exist in the database."""
    pass


class FeedbackNotFoundError(NotFoundError):
    """Raised when a feedback record is not found by ID or request ID."""
    pass


# -----------------------------------------------------------------------------
# Validation Exceptions
# -----------------------------------------------------------------------------


class ValidationError(AppError):
    """Base exception for input or business rule validation errors."""
    pass


class InvalidDescriptionError(ValidationError):
    """Raised when request description is missing, empty, or invalid."""
    pass


class InvalidRequestDateError(ValidationError):
    """Raised when request submission date is invalid or in the future."""
    pass


class DuplicateRequestNumberError(ValidationError):
    """Raised when the request number already exists in the database."""
    pass


class ImmutableFieldError(ValidationError):
    """Raised when attempting to modify an immutable or non-whitelisted request field."""
    pass


class InvalidFilterError(ValidationError):
    """Raised when invalid or unparsable search/listing filters are supplied."""
    pass


class InvalidAssignmentStatusError(ValidationError):
    """Raised when an assignment status is not in the approved lifecycle model."""
    pass


class InvalidDateError(ValidationError):
    """Raised when dates violate logical or temporal constraints (e.g., due_date < assigned_date)."""
    pass


class InvalidHoursSpentError(ValidationError):
    """Raised when work log hours spent is negative or invalid."""
    pass


class InvalidWorkDescriptionError(ValidationError):
    """Raised when work log description is missing, empty, or invalid."""
    pass


class InsufficientMaterialStockError(ValidationError):
    """Raised when requested material quantity exceeds current warehouse stock."""
    pass


class InvalidMaterialQuantityError(ValidationError):
    """Raised when material quantity is zero, negative, or invalid."""
    pass


class DuplicateMaterialUsageError(ValidationError):
    """Raised when material has already been issued for the specified work log."""
    pass


class InvalidMaterialUsageError(ValidationError):
    """Raised when material usage parameters are missing or invalid."""
    pass


class InvalidCostError(ValidationError):
    """Raised when cost fields or parameters violate business rules."""
    pass


class InvalidStatusTransitionError(ValidationError):
    """Raised when an unapproved request status transition is attempted."""
    pass


class SameStatusUpdateError(InvalidStatusTransitionError):
    """Raised when attempting to transition a request to its current status."""
    pass


class InvalidResolutionDescriptionError(ValidationError):
    """Raised when request closure resolution description is missing, empty, or whitespace."""
    pass


class InvalidClosureTransitionError(InvalidStatusTransitionError):
    """Raised when attempting to close a request that is not in an eligible status."""
    pass


class AlreadyClosedError(SameStatusUpdateError):
    """Raised when attempting to close a request that is already in Closed status."""
    pass


class InvalidClosureDateError(InvalidDateError):
    """Raised when closure date is invalid, missing, or precedes request_date."""
    pass


class DuplicateFeedbackError(ValidationError):
    """Raised when attempting to submit duplicate feedback for a maintenance request."""
    pass


class InvalidRatingError(ValidationError):
    """Raised when feedback rating is not an integer between 1 and 5."""
    pass


class RequestNotClosedError(ValidationError):
    """Raised when attempting to submit feedback for a request that is not in Closed status."""
    pass


# -----------------------------------------------------------------------------
# Database / Transaction Exceptions
# -----------------------------------------------------------------------------


class DatabaseOperationError(AppError):
    """Raised when a low-level database or transaction failure occurs."""
    pass

