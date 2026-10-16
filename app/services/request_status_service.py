"""
Request Status Service Module
Dedicated service coordinating maintenance request status changes and audit trail logging.
Enforces the approved lifecycle:
    Open -> Assigned -> In Progress <-> On Hold -> Closed
Guarantees transaction atomicity and row-level locking consistency.
"""

from __future__ import annotations

from app.services.request_service import (
    ALLOWED_TRANSITIONS,
    RequestService,
)

# RequestStatusService inherits all request and status transition capabilities
class RequestStatusService(RequestService):
    """Specialized service for request status workflows and status history tracking."""
    pass
