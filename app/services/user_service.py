"""
User Service Module
Coordinates campus user self-registration and profile management.
Enforces validation invariants, allowed self-registration roles, and email uniqueness.
"""

from __future__ import annotations

import re
from typing import Any
import psycopg

from app.db import DatabaseManager, get_db_manager
from app.exceptions import ValidationError
from app.repositories.user import UserRepository
from app.utils.logger import get_logger

logger = get_logger(__name__)

ALLOWED_REGISTRATION_ROLES = frozenset({"Student", "Faculty", "Staff"})
FORBIDDEN_REGISTRATION_ROLES = frozenset({"Facility Manager", "Technician", "Admin"})

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserService:
    """Service layer managing campus user registration and identity validation."""

    def __init__(
        self,
        user_repo: UserRepository | None = None,
        db_manager: DatabaseManager | None = None,
    ) -> None:
        self.user_repo = user_repo or UserRepository()
        self.db_manager = db_manager or get_db_manager()

    def register_user(
        self,
        full_name: str | None,
        email: str | None,
        account_type: str | None,
        phone: str | None = None,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """
        Validate and create a new campus requester account.
        Only 'Student', 'Faculty', and 'Staff' accounts can be self-registered.
        """
        # 1. Full Name validation
        if not full_name or not str(full_name).strip():
            raise ValidationError("Full Name is required")
        clean_name = str(full_name).strip()
        if len(clean_name) > 100:
            raise ValidationError("Full Name cannot exceed 100 characters")

        # 2. Email validation
        if not email or not str(email).strip():
            raise ValidationError("Email is required")
        clean_email = str(email).strip().lower()
        if not EMAIL_REGEX.match(clean_email):
            raise ValidationError("Invalid email format")
        if len(clean_email) > 255:
            raise ValidationError("Email cannot exceed 255 characters")

        # 3. Account Type / Role validation
        if not account_type or not str(account_type).strip():
            raise ValidationError("Account Type is required")
        clean_role_input = str(account_type).strip()

        # Check forbidden roles first
        if any(f.lower() == clean_role_input.lower() for f in FORBIDDEN_REGISTRATION_ROLES):
            raise ValidationError(
                f"Self-registration is not permitted for '{clean_role_input}'. "
                "Administrative and technician accounts are provisioned by system administrators."
            )

        # Check allowed roles
        matched_role = None
        for allowed in ALLOWED_REGISTRATION_ROLES:
            if allowed.lower() == clean_role_input.lower():
                matched_role = allowed
                break

        if not matched_role:
            allowed_list = ", ".join(sorted(ALLOWED_REGISTRATION_ROLES))
            raise ValidationError(
                f"Invalid account type '{clean_role_input}'. Allowed account types are: {allowed_list}"
            )

        # 4. Phone validation (optional)
        clean_phone = str(phone).strip() if phone and str(phone).strip() else None
        if clean_phone and len(clean_phone) > 20:
            raise ValidationError("Phone number cannot exceed 20 characters")

        # 5. Check Email Uniqueness
        if self.user_repo.is_email_taken(clean_email, conn=conn):
            raise ValidationError("An account with this email already exists.")

        # 6. Retrieve Role from DB
        role_row = self.user_repo.get_role_by_name(matched_role, conn=conn)
        if not role_row:
            raise ValidationError(f"Role '{matched_role}' not found in database")

        # 7. Create User
        user_data = {
            "full_name": clean_name,
            "email": clean_email,
            "phone": clean_phone,
            "role_id": role_row["role_id"],
            "status": "Active",
        }
        created = self.user_repo.create_user(user_data, conn=conn)

        logger.info(
            "Registered new %s user %s (ID %s, email %s)",
            matched_role,
            clean_name,
            created["user_id"],
            clean_email,
        )

        return {
            "user_id": created["user_id"],
            "full_name": created["full_name"],
            "email": created["email"],
            "phone": created["phone"],
            "role_id": created["role_id"],
            "role_name": matched_role,
            "portal_role": "requester",
            "status": created["status"],
        }
