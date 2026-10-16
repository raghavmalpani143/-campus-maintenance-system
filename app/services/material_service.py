"""
Material Service Module
Coordinates material inventory consumption, stock validation, and financial ledger logging.
Enforces the single-ledger COST model:
    Actual Material Cost = QuantityUsed * UnitCost
Guarantees atomicity via row-level locking (SELECT ... FOR UPDATE) and rollback on any failure.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, DecimalException
from typing import Any
import psycopg
import psycopg.errors

from app.db import DatabaseManager, get_db_manager
from app.exceptions import (
    AppError,
    CostNotFoundError,
    DatabaseOperationError,
    DuplicateMaterialUsageError,
    InsufficientMaterialStockError,
    InvalidDateError,
    InvalidFilterError,
    InvalidMaterialQuantityError,
    InvalidMaterialUsageError,
    MaterialNotFoundError,
    NotFoundError,
    TechnicianNotFoundError,
    ValidationError,
    WorkLogNotFoundError,
)
from app.repositories.cost import CostRepository
from app.repositories.material import MaterialRepository
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MaterialService:
    """Service layer managing material inventory, requisitions, and atomic ledger cost creation."""

    def __init__(
        self,
        material_repo: MaterialRepository | None = None,
        cost_repo: CostRepository | None = None,
        db_manager: DatabaseManager | None = None,
    ) -> None:
        self.material_repo = material_repo or MaterialRepository()
        self.cost_repo = cost_repo or CostRepository()
        self.db_manager = db_manager or get_db_manager()

    def record_material_usage(
        self,
        work_log_id: int,
        material_id: int,
        quantity_used: float | Decimal | int,
        issued_by: int,
        issued_date: datetime | None = None,
        cost_date: datetime | None = None,
        description: str | None = None,
        unit_price: float | Decimal | int | None = None,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """
        Record material consumption against an existing work log within an atomic transaction.
        
        Execution steps:
        1. Validate work log existence and resolve its parent request_id
        2. Validate issuing technician existence
        3. Validate input parameters and positive quantity
        4. Validate documented date formats and optional unit_price
        5. Check for duplicate material usage on (work_log_id, material_id)
        6. Acquire row-level lock on material (SELECT ... FOR UPDATE)
        7. Verify available stock >= quantity_used
        8. Insert WORK_LOG_MATERIAL junction row
        9. Atomically decrement MATERIAL.stock_qty
        10. Insert exactly one corresponding COST row (CostType='Material') with immutable locked amount
        11. Commit transaction and return hydrated usage record
        """
        # 1. Validate required fields presence
        if work_log_id is None:
            raise InvalidMaterialUsageError("Work log ID is required")
        if material_id is None:
            raise InvalidMaterialUsageError("Material ID is required")
        if quantity_used is None:
            raise InvalidMaterialUsageError("Quantity used is required")
        if issued_by is None:
            raise InvalidMaterialUsageError("Issued-by technician ID is required")

        if not isinstance(work_log_id, int) or work_log_id <= 0:
            raise InvalidMaterialUsageError(f"Work log ID must be a positive integer: {work_log_id}")
        if not isinstance(material_id, int) or material_id <= 0:
            raise InvalidMaterialUsageError(f"Material ID must be a positive integer: {material_id}")
        if not isinstance(issued_by, int) or issued_by <= 0:
            raise InvalidMaterialUsageError(f"Issued-by technician ID must be a positive integer: {issued_by}")

        # 2. Validate quantity (strictly positive numeric value)
        try:
            numeric_quantity = Decimal(str(quantity_used))
        except (ValueError, TypeError, DecimalException) as err:
            raise InvalidMaterialQuantityError(f"Quantity used must be numeric: {quantity_used}") from err

        if numeric_quantity <= 0:
            raise InvalidMaterialQuantityError(f"Quantity used must be strictly positive: {numeric_quantity}")

        # 3. Validate unit price if provided
        effective_unit_price: Decimal | None = None
        if unit_price is not None:
            try:
                effective_unit_price = Decimal(str(unit_price))
            except (ValueError, TypeError, DecimalException) as err:
                raise ValidationError(f"Unit price must be numeric: {unit_price}") from err
            if effective_unit_price < 0:
                raise ValidationError(f"Unit price must be non-negative: {effective_unit_price}")

        # 4. Validate dates
        effective_issued_date = issued_date if issued_date is not None else datetime.now()
        if not isinstance(effective_issued_date, datetime):
            raise InvalidDateError("Issued date must be a valid datetime instance")

        effective_cost_date = cost_date if cost_date is not None else effective_issued_date
        if not isinstance(effective_cost_date, datetime):
            raise InvalidDateError("Cost date must be a valid datetime instance")

        # 5. Execute atomic transaction
        try:
            if conn is not None:
                with conn.transaction():
                    return self._execute_record_material_usage(
                        conn=conn,
                        work_log_id=work_log_id,
                        material_id=material_id,
                        quantity_used=numeric_quantity,
                        issued_by=issued_by,
                        issued_date=effective_issued_date,
                        cost_date=effective_cost_date,
                        description=description,
                        unit_price=effective_unit_price,
                    )
            else:
                with self.db_manager.transaction() as managed_conn:
                    return self._execute_record_material_usage(
                        conn=managed_conn,
                        work_log_id=work_log_id,
                        material_id=material_id,
                        quantity_used=numeric_quantity,
                        issued_by=issued_by,
                        issued_date=effective_issued_date,
                        cost_date=effective_cost_date,
                        description=description,
                        unit_price=effective_unit_price,
                    )
        except AppError:
            raise
        except psycopg.errors.UniqueViolation as err:
            logger.warning("Duplicate material usage caught by unique constraint: %s", err)
            raise DuplicateMaterialUsageError(
                f"Material ID {material_id} has already been recorded for work log {work_log_id}"
            ) from err
        except psycopg.errors.CheckViolation as err:
            err_str = str(err)
            if "chk_wlm_quantity_used" in err_str:
                raise InvalidMaterialQuantityError("Quantity used must be strictly positive") from err
            elif "chk_material_stock_qty" in err_str:
                raise InsufficientMaterialStockError("Material stock quantity cannot be negative") from err
            raise ValidationError(f"Check constraint violation: {err}") from err
        except psycopg.errors.RaiseException as err:
            if "Insufficient stock" in str(err):
                raise InsufficientMaterialStockError(str(err)) from err
            raise ValidationError(str(err)) from err
        except Exception as err:
            logger.error("Failed to execute material usage transaction: %s", err, exc_info=True)
            raise DatabaseOperationError(f"Database error during material usage recording: {err}") from err

    def _execute_record_material_usage(
        self,
        conn: psycopg.Connection,
        work_log_id: int,
        material_id: int,
        quantity_used: Decimal,
        issued_by: int,
        issued_date: datetime,
        cost_date: datetime,
        description: str | None,
        unit_price: Decimal | None = None,
    ) -> dict[str, Any]:
        """Internal helper executing the atomic material consumption sequence."""
        # 1. Verify WORK_LOG exists and resolve parent request_id
        wl_ctx = self.material_repo.get_work_log_context(work_log_id, conn=conn)
        if wl_ctx is None:
            raise WorkLogNotFoundError(f"Work log with ID {work_log_id} does not exist")
        request_id = wl_ctx["request_id"]
        request_number = wl_ctx["request_number"]

        # 2. Verify ISSUED_BY technician exists
        if not self.material_repo.technician_exists(issued_by, conn=conn):
            raise TechnicianNotFoundError(f"Technician with ID {issued_by} does not exist")

        # 3. Check for DUPLICATE material usage
        if self.material_repo.work_log_material_exists(work_log_id, material_id, conn=conn):
            raise DuplicateMaterialUsageError(
                f"Material ID {material_id} has already been recorded for work log {work_log_id}"
            )

        # 4. Lock and read MATERIAL row safely (FOR UPDATE)
        material = self.material_repo.get_material_for_update(material_id, conn=conn)
        if material is None:
            raise MaterialNotFoundError(f"Material with ID {material_id} does not exist")

        # 5. Verify sufficient available stock
        current_stock = material["stock_qty"]
        if quantity_used > current_stock:
            raise InsufficientMaterialStockError(
                f"Insufficient stock for material '{material['material_name']}' (ID: {material_id}). "
                f"Available: {current_stock}, requested: {quantity_used}"
            )

        # 6. Read UnitCost and calculate actual usage cost (locked immutable price)
        if unit_price is not None:
            unit_cost = unit_price
        else:
            unit_cost = Decimal(str(material["unit_cost"]))
        actual_material_cost = (quantity_used * unit_cost).quantize(Decimal("0.01"))

        # 7. Insert WORK_LOG_MATERIAL junction row
        # (Trigger trg_check_material_stock validates against pre-decrement stock)
        self.material_repo.create_work_log_material(
            data={
                "work_log_id": work_log_id,
                "material_id": material_id,
                "quantity_used": quantity_used,
                "issued_date": issued_date,
                "issued_by": issued_by,
            },
            conn=conn,
        )

        # 8. Atomically decrement MATERIAL.stock_qty
        updated_material = self.material_repo.decrement_stock(
            material_id=material_id,
            quantity=quantity_used,
            conn=conn,
        )

        # 9. Insert exactly one corresponding COST row (CostType = 'Material')
        if description and description.strip():
            cost_description = description.strip()
        else:
            cost_description = (
                f"[WLM:{work_log_id}:{material_id}] {quantity_used} {material['unit']} {material['material_name']} "
                f"issued for work log #{work_log_id} @ ₹{unit_cost:.2f}/unit"
            )

        cost_record = self.cost_repo.create_cost(
            data={
                "request_id": request_id,
                "cost_type": "Material",
                "amount": actual_material_cost,
                "cost_date": cost_date,
                "description": cost_description,
            },
            conn=conn,
        )

        # 10. Retrieve joined material usage and enrich with cost details
        hydrated_usage = self.material_repo.get_material_usage(work_log_id, material_id, conn=conn)
        if not hydrated_usage:
            raise DatabaseOperationError(
                f"Failed to retrieve material usage for WorkLog {work_log_id} and Material {material_id}"
            )

        remaining = updated_material["stock_qty"] if updated_material else current_stock - quantity_used
        hydrated_usage["cost_id"] = cost_record["cost_id"]
        hydrated_usage["cost"] = cost_record
        hydrated_usage["remaining_stock"] = remaining
        hydrated_usage["unit_price"] = float(unit_cost)
        hydrated_usage["unit_cost"] = float(unit_cost)
        hydrated_usage["total_cost"] = float(actual_material_cost)
        hydrated_usage["calculated_usage_cost"] = float(actual_material_cost)

        logger.info(
            "Recorded material usage: WorkLog=%s, Material=%s (%s), Qty=%s, Cost=₹%s, CostID=%s, RemainingStock=%s",
            work_log_id,
            material_id,
            material["material_name"],
            quantity_used,
            actual_material_cost,
            cost_record["cost_id"],
            remaining,
        )
        return hydrated_usage

    def request_material(
        self,
        material_name: str,
        quantity: float | Decimal | int,
        unit_price: float | Decimal | int,
        technician_id: int,
        assignment_id: int | None = None,
        work_log_id: int | None = None,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """
        Record technician material request / usage with an immutable unit price.
        Validates non-empty name, positive quantity, non-negative unit price,
        technician work order authorization, and records into single-ledger COST.
        """
        if not material_name or not isinstance(material_name, str) or not material_name.strip():
            raise ValidationError("Material name is required and cannot be empty")
        clean_name = material_name.strip()

        if quantity is None:
            raise InvalidMaterialQuantityError("Quantity is required")
        try:
            num_qty = Decimal(str(quantity))
        except (ValueError, TypeError, DecimalException) as err:
            raise InvalidMaterialQuantityError(f"Quantity must be numeric: {quantity}") from err
        if num_qty <= 0:
            raise InvalidMaterialQuantityError("Quantity must be strictly positive")

        if unit_price is None:
            raise ValidationError("Unit price is required")
        try:
            num_price = Decimal(str(unit_price))
        except (ValueError, TypeError, DecimalException) as err:
            raise ValidationError(f"Unit price must be numeric: {unit_price}") from err
        if num_price < 0:
            raise ValidationError("Unit price must be non-negative")

        if technician_id is None or not isinstance(technician_id, int) or technician_id <= 0:
            raise TechnicianNotFoundError(f"Valid technician ID is required: {technician_id}")

        if assignment_id is None and work_log_id is None:
            raise ValidationError("Either assignment_id or work_log_id is required")

        try:
            if conn is not None:
                with conn.transaction():
                    return self._execute_request_material(
                        conn=conn,
                        clean_name=clean_name,
                        num_qty=num_qty,
                        num_price=num_price,
                        technician_id=technician_id,
                        assignment_id=assignment_id,
                        work_log_id=work_log_id,
                    )
            else:
                with self.db_manager.transaction() as managed_conn:
                    return self._execute_request_material(
                        conn=managed_conn,
                        clean_name=clean_name,
                        num_qty=num_qty,
                        num_price=num_price,
                        technician_id=technician_id,
                        assignment_id=assignment_id,
                        work_log_id=work_log_id,
                    )
        except AppError:
            raise
        except Exception as err:
            logger.error("Failed to execute material request: %s", err, exc_info=True)
            raise DatabaseOperationError(f"Database error during material request: {err}") from err

    def _execute_request_material(
        self,
        conn: psycopg.Connection,
        clean_name: str,
        num_qty: Decimal,
        num_price: Decimal,
        technician_id: int,
        assignment_id: int | None,
        work_log_id: int | None,
    ) -> dict[str, Any]:
        """Internal helper executing material request resolution and recording."""
        if not self.material_repo.technician_exists(technician_id, conn=conn):
            raise TechnicianNotFoundError(f"Technician with ID {technician_id} does not exist")

        target_assignment_id: int
        target_work_log_id: int

        if assignment_id is not None:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT assignment_id, request_id, technician_id FROM assignment WHERE assignment_id = %(id)s;",
                    {"id": assignment_id},
                )
                assign_row = cur.fetchone()
            if not assign_row:
                raise NotFoundError(f"Assignment with ID {assignment_id} does not exist")
            if int(assign_row["technician_id"]) != int(technician_id):
                raise ValidationError(
                    f"Technician ID {technician_id} is not permitted to request materials for "
                    f"assignment ID {assignment_id} belonging to technician ID {assign_row['technician_id']}"
                )
            target_assignment_id = assignment_id

            if work_log_id is None:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT work_log_id FROM work_log WHERE assignment_id = %(aid)s ORDER BY work_log_id DESC LIMIT 1;",
                        {"aid": assignment_id},
                    )
                    existing_wl = cur.fetchone()
                if existing_wl:
                    target_work_log_id = existing_wl["work_log_id"]
                else:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO work_log (assignment_id, work_date, work_description, hours_spent)
                            VALUES (%(aid)s, CURRENT_TIMESTAMP, %(desc)s, 0.0)
                            RETURNING work_log_id;
                            """,
                            {"aid": assignment_id, "desc": f"Material requisition: {clean_name}"},
                        )
                        target_work_log_id = cur.fetchone()["work_log_id"]
            else:
                target_work_log_id = work_log_id
        else:
            wl_ctx = self.material_repo.get_work_log_context(work_log_id, conn=conn)
            if not wl_ctx:
                raise WorkLogNotFoundError(f"Work log with ID {work_log_id} does not exist")
            if int(wl_ctx["assigned_technician_id"]) != int(technician_id):
                raise ValidationError(
                    f"Technician ID {technician_id} is not permitted to request materials for "
                    f"work log ID {work_log_id} assigned to technician ID {wl_ctx['assigned_technician_id']}"
                )
            target_assignment_id = wl_ctx["assignment_id"]
            target_work_log_id = work_log_id

        # Catalog resolution or auto-registration
        mat = self.material_repo.get_material_by_name(clean_name, conn=conn)
        if mat:
            mat_id = mat["material_id"]
            if mat["stock_qty"] < num_qty:
                raise InsufficientMaterialStockError(
                    f"Insufficient stock for material '{mat['material_name']}' (ID: {mat_id}). "
                    f"Available: {mat['stock_qty']}, requested: {num_qty}"
                )
        else:
            new_mat = self.material_repo.create_material(
                {
                    "material_name": clean_name,
                    "unit": "Piece",
                    "unit_cost": num_price,
                    "stock_qty": max(100, int(num_qty) * 2),
                    "status": "Active",
                },
                conn=conn,
            )
            mat_id = new_mat["material_id"]

        # Ensure no composite PK collision on (target_work_log_id, mat_id)
        if self.material_repo.work_log_material_exists(target_work_log_id, mat_id, conn=conn):
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO work_log (assignment_id, work_date, work_description, hours_spent)
                    VALUES (%(aid)s, CURRENT_TIMESTAMP, %(desc)s, 0.0)
                    RETURNING work_log_id;
                    """,
                    {"aid": target_assignment_id, "desc": f"Material requisition: {clean_name}"},
                )
                target_work_log_id = cur.fetchone()["work_log_id"]

        usage = self._execute_record_material_usage(
            conn=conn,
            work_log_id=target_work_log_id,
            material_id=mat_id,
            quantity_used=num_qty,
            issued_by=technician_id,
            issued_date=datetime.now(),
            cost_date=datetime.now(),
            description=f"[WLM:{target_work_log_id}:{mat_id}] {num_qty}x {clean_name} @ ₹{num_price:.2f}/unit",
            unit_price=num_price,
        )
        usage["assignment_id"] = target_assignment_id
        usage["total"] = float((num_qty * num_price).quantize(Decimal("0.01")))
        return usage


    def get_material_usage(
        self,
        work_log_id: int,
        material_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """Retrieve material usage entry by composite key or raise NotFoundError."""
        if work_log_id is None or not isinstance(work_log_id, int) or work_log_id <= 0:
            raise InvalidMaterialUsageError(f"Work log ID must be a positive integer: {work_log_id}")
        if material_id is None or not isinstance(material_id, int) or material_id <= 0:
            raise InvalidMaterialUsageError(f"Material ID must be a positive integer: {material_id}")

        usage = self.material_repo.get_material_usage(work_log_id, material_id, conn=conn)
        if not usage:
            raise NotFoundError(
                f"Material usage not found for work log ID {work_log_id} and material ID {material_id}"
            )
        return usage

    def list_material_usage(
        self,
        filters: dict[str, Any] | None = None,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """List and filter material usage entries with validated filter criteria."""
        filters = filters or {}
        limit = filters.get("limit", 100)
        offset = filters.get("offset", 0)

        if not isinstance(limit, int) or limit < 1:
            raise InvalidFilterError("Limit filter must be a positive integer")
        if not isinstance(offset, int) or offset < 0:
            raise InvalidFilterError("Offset filter must be a non-negative integer")

        if "date_from" in filters and filters["date_from"] is not None:
            if not isinstance(filters["date_from"], datetime):
                raise InvalidDateError("date_from must be a valid datetime instance")

        if "date_to" in filters and filters["date_to"] is not None:
            if not isinstance(filters["date_to"], datetime):
                raise InvalidDateError("date_to must be a valid datetime instance")

        return self.material_repo.list_material_usage(filters=filters, conn=conn)

    def get_material_by_id(
        self,
        material_id: int,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        """Retrieve material catalog item by ID or raise MaterialNotFoundError."""
        if material_id is None or not isinstance(material_id, int) or material_id <= 0:
            raise InvalidMaterialUsageError(f"Material ID must be a positive integer: {material_id}")

        material = self.material_repo.get_material_by_id(material_id, conn=conn)
        if not material:
            raise MaterialNotFoundError(f"Material with ID {material_id} does not exist")
        return material

    def list_materials(
        self,
        filters: dict[str, Any] | None = None,
        conn: psycopg.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """List materials from the catalog with validated pagination."""
        filters = filters or {}
        limit = filters.get("limit", 100)
        offset = filters.get("offset", 0)

        if not isinstance(limit, int) or limit < 1:
            raise InvalidFilterError("Limit filter must be a positive integer")
        if not isinstance(offset, int) or offset < 0:
            raise InvalidFilterError("Offset filter must be a non-negative integer")

        return self.material_repo.list_materials(filters=filters, conn=conn)
