"""
Phase 4 FastAPI Server Module
Connects the locked Phase 3 services and locked Phase 2 reporting views
to the modern developer dashboard frontend.
All business rules, state transitions, row locks, inventory deductions,
and cost records are delegated directly to authoritative Phase 3 services.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
import os

from fastapi import Body, FastAPI, Header, HTTPException, Query, status as http_status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.db import get_connection
from app.exceptions import (
    AppError,
    DatabaseOperationError,
    NotFoundError,
    ValidationError,
)
from app.repositories.report import ReportRepository
from app.services import (
    AssignmentService,
    CostService,
    FeedbackService,
    MaterialService,
    RequestClosureService,
    RequestService,
    RequestStatusService,
    TechnicianService,
    UserService,
    WorkLogService,
)
from app.utils.logger import get_logger

logger = get_logger("app.server")

# Instantiate authoritative services
request_service = RequestService()
assignment_service = AssignmentService()
work_log_service = WorkLogService()
material_service = MaterialService()
cost_service = CostService()
status_service = RequestStatusService()
closure_service = RequestClosureService()
feedback_service = FeedbackService()
technician_service = TechnicianService()
user_service = UserService()
report_repo = ReportRepository()

app = FastAPI(
    title="Campus Facility Maintenance Operations API",
    description="Backend API server powering the Developer Operations Dashboard for Campus Facility Maintenance (Project #41)",
    version="1.0.0",
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def serialize_entity(obj: Any) -> Any:
    """Helper recursively serializing datetimes, dates, and decimals for JSON responses."""
    if isinstance(obj, dict):
        return {k: serialize_entity(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize_entity(v) for v in obj]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return obj


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Any, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=http_status.HTTP_404_NOT_FOUND,
        content={"error": type(exc).__name__, "message": str(exc)},
    )


@app.exception_handler(ValidationError)
async def validation_handler(request: Any, exc: ValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=http_status.HTTP_400_BAD_REQUEST,
        content={"error": type(exc).__name__, "message": str(exc)},
    )


@app.exception_handler(DatabaseOperationError)
async def db_error_handler(request: Any, exc: DatabaseOperationError) -> JSONResponse:
    return JSONResponse(
        status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": type(exc).__name__, "message": str(exc)},
    )


@app.exception_handler(AppError)
async def app_error_handler(request: Any, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=http_status.HTTP_400_BAD_REQUEST,
        content={"error": type(exc).__name__, "message": str(exc)},
    )


# =============================================================================
# METADATA & LOOKUPS
# =============================================================================

@app.get("/api/lookups")
def get_lookups() -> dict[str, Any]:
    """Retrieve reference lookup metadata for dropdowns in modals and filter bars."""
    return serialize_entity(report_repo.get_lookup_data())


@app.get("/api/dashboard/stats")
def get_dashboard_stats() -> dict[str, Any]:
    """Calculate live operational dashboard KPI counters."""
    requests = request_service.list_requests({"limit": 500})
    open_count = sum(1 for r in requests if r["status_name"] == "Open")
    active_count = sum(1 for r in requests if r["status_name"] in ("Assigned", "In Progress"))
    on_hold_count = sum(1 for r in requests if r["status_name"] == "On Hold")
    closed_count = sum(1 for r in requests if r["status_name"] == "Closed")

    materials = material_service.list_materials()
    low_stock = sum(1 for m in materials if m["stock_qty"] <= 5)

    costs = cost_service.list_costs({"limit": 500})
    total_expenditure = sum(float(c["amount"]) for c in costs)

    return {
        "open_requests": open_count,
        "active_jobs": active_count,
        "on_hold": on_hold_count,
        "closed": closed_count,
        "total_requests": len(requests),
        "low_stock_materials": low_stock,
        "total_expenditure": round(total_expenditure, 2),
    }


# =============================================================================
# DEMO IDENTITY & ROLE RESOLUTION (College Demo Only)
# =============================================================================

@app.post("/api/auth/demo-login")
def demo_login(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """
    Lightweight Demo Identity Resolution for College Project Demonstration.
    Resolves registered campus email against existing USER or TECHNICIAN records.
    Maps Facility Manager to 'admin', Student/Faculty/Staff to 'requester', and
    Technicians to 'technician'.
    """
    raw_email = payload.get("email", "").strip()
    if not raw_email:
        raise ValidationError("Registered campus email is required")

    email = raw_email.lower()

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Check USER table
            cur.execute("""
                SELECT u.user_id, u.full_name, u.email, u.status, u.role_id, r.role_name
                FROM "user" u
                JOIN role r ON u.role_id = r.role_id
                WHERE LOWER(u.email) = %(email)s;
            """, {"email": email})
            user_row = cur.fetchone()

            if user_row:
                if user_row["status"] != "Active":
                    raise ValidationError(f"User account for {user_row['full_name']} is inactive")

                # Facility Manager -> admin, Student/Faculty/Staff -> requester
                if user_row["role_id"] == 4 or user_row["role_name"] == "Facility Manager":
                    portal_role = "admin"
                else:
                    portal_role = "requester"

                return {
                    "entity_type": "user",
                    "user_id": user_row["user_id"],
                    "full_name": user_row["full_name"],
                    "email": user_row["email"],
                    "role_id": user_row["role_id"],
                    "role_name": user_row["role_name"],
                    "portal_role": portal_role,
                }

            # 2. Check TECHNICIAN table
            cur.execute("""
                SELECT technician_id, full_name, email, department, status, labor_rate
                FROM technician
                WHERE LOWER(email) = %(email)s;
            """, {"email": email})
            tech_row = cur.fetchone()

            if tech_row:
                if tech_row["status"] != "Active":
                    raise ValidationError(f"Technician account for {tech_row['full_name']} is inactive")

                return {
                    "entity_type": "technician",
                    "technician_id": tech_row["technician_id"],
                    "full_name": tech_row["full_name"],
                    "email": tech_row["email"],
                    "department": tech_row["department"],
                    "labor_rate": float(tech_row["labor_rate"]),
                    "role_name": f"Technician ({tech_row['department']})",
                    "portal_role": "technician",
                }

    raise NotFoundError(f"No registered campus account found for email: {raw_email}")


@app.post("/api/auth/register", status_code=http_status.HTTP_201_CREATED)
def register_account(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """
    Self-register a new campus requester account (Student, Faculty, Staff).
    Enforces validation, uniqueness, and rejects unauthorized roles.
    """
    full_name = payload.get("full_name")
    email = payload.get("email")
    account_type = payload.get("account_type") or payload.get("role_name")
    phone = payload.get("phone")

    created = user_service.register_user(
        full_name=full_name,
        email=email,
        account_type=account_type,
        phone=phone,
    )
    return serialize_entity(created)


@app.get("/api/auth/demo-accounts")
def list_demo_accounts() -> list[dict[str, Any]]:
    """Return active sample accounts across Requester, Admin, and Technician roles for 1-click demo selection."""
    accounts = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.user_id, u.full_name, u.email, r.role_name,
                       CASE WHEN u.role_id = 4 THEN 'admin' ELSE 'requester' END as portal_role
                FROM "user" u
                JOIN role r ON u.role_id = r.role_id
                WHERE u.status = 'Active'
                ORDER BY u.role_id DESC, u.user_id ASC;
            """)
            for u in cur.fetchall():
                accounts.append({
                    "id": u["user_id"],
                    "name": u["full_name"],
                    "email": u["email"],
                    "role": u["role_name"],
                    "portal_role": u["portal_role"],
                })

            cur.execute("""
                SELECT technician_id, full_name, email, department, status, labor_rate
                FROM technician
                WHERE status = 'Active'
                ORDER BY technician_id ASC;
            """)
            for t in cur.fetchall():
                accounts.append({
                    "id": t["technician_id"],
                    "name": t["full_name"],
                    "email": t["email"],
                    "department": t["department"],
                    "role": f"Technician ({t['department']})",
                    "portal_role": "technician",
                })
    return accounts


# =============================================================================
# ROLE-SPECIFIC DASHBOARDS (Requester & Technician)
# =============================================================================

@app.get("/api/requester/{user_id}/dashboard")
def get_requester_dashboard(user_id: int) -> dict[str, Any]:
    """
    Provide aggregated metrics and own requests for the requester portal.
    Restricted exclusively to requests created by user_id.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT user_id, full_name, email, status FROM "user" WHERE user_id = %(uid)s;', {"uid": user_id})
            user_row = cur.fetchone()
            if not user_row:
                raise NotFoundError(f"User ID {user_id} not found")

    my_requests = request_service.list_requests({"requested_by": user_id, "limit": 100})

    counts = {
        "total": len(my_requests),
        "open": sum(1 for r in my_requests if r.get("status_name") == "Open"),
        "in_progress": sum(1 for r in my_requests if r.get("status_name") == "In Progress"),
        "on_hold": sum(1 for r in my_requests if r.get("status_name") == "On Hold"),
        "closed": sum(1 for r in my_requests if r.get("status_name") == "Closed"),
    }

    return serialize_entity({
        "user": user_row,
        "counts": counts,
        "requests": my_requests,
    })


@app.get("/api/technician/{technician_id}/dashboard")
def get_technician_dashboard(technician_id: int) -> dict[str, Any]:
    """
    Provide technician-specific active assignments, work logs, and issued materials.
    Restricted exclusively to technician_id.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT technician_id, full_name, email, department, status, labor_rate 
                FROM technician WHERE technician_id = %(tid)s;
            """, {"tid": technician_id})
            tech_row = cur.fetchone()
            if not tech_row:
                raise NotFoundError(f"Technician ID {technician_id} not found")

            # Enrich assignments with location and priority metadata for field operations
            cur.execute("""
                SELECT 
                    a.assignment_id,
                    r.description AS description,
                    b.building_name,
                    rm.room_number,
                    p.priority_level
                FROM assignment a
                JOIN request r ON a.request_id = r.request_id
                LEFT JOIN room rm ON r.room_id = rm.room_id
                LEFT JOIN building b ON rm.building_id = b.building_id
                LEFT JOIN priority p ON r.priority_id = p.priority_id
                WHERE a.technician_id = %(tid)s;
            """, {"tid": technician_id})
            meta_by_id = {row["assignment_id"]: row for row in cur.fetchall()}

    my_assignments = assignment_service.list_assignments({"technician_id": technician_id, "limit": 100})
    for a in my_assignments:
        if "status" not in a and "assignment_status" in a:
            a["status"] = a["assignment_status"]
        meta = meta_by_id.get(a["assignment_id"])
        if meta:
            if not a.get("description"):
                a["description"] = meta.get("description")
            a["building_name"] = meta.get("building_name")
            a["room_number"] = meta.get("room_number")
            a["priority_level"] = meta.get("priority_level")

    my_work_logs = work_log_service.list_work_logs({"technician_id": technician_id, "limit": 100})
    my_materials = material_service.list_material_usage({"technician_id": technician_id, "limit": 100})

    # Retrieve incoming unassigned requests matching technician's department/category domain
    incoming_requests = technician_service.get_incoming_requests_for_technician(technician_id)

    total_hours = sum(Decimal(str(wl.get("hours_spent", 0))) for wl in my_work_logs)
    active_jobs = sum(1 for a in my_assignments if (a.get("status") or a.get("assignment_status")) in ("Assigned", "In Progress"))
    completed_jobs = sum(1 for a in my_assignments if (a.get("status") or a.get("assignment_status")) == "Completed")

    return serialize_entity({
        "technician": tech_row,
        "counts": {
            "total_assignments": len(my_assignments),
            "active_jobs": active_jobs,
            "completed_jobs": completed_jobs,
            "total_hours": float(total_hours),
            "incoming_requests": len(incoming_requests),
        },
        "incoming_requests": incoming_requests,
        "assignments": my_assignments,
        "work_logs": my_work_logs,
        "materials": my_materials,
    })


@app.get("/api/technician/{technician_id}/incoming-requests")
def get_technician_incoming_requests(technician_id: int) -> list[dict[str, Any]]:
    """Retrieve unassigned, incoming requests belonging strictly to the technician's department."""
    incoming = technician_service.get_incoming_requests_for_technician(technician_id)
    return serialize_entity(incoming)


# =============================================================================
# REQUESTS (Phase 3B, 3E, 3F, 3G)
# =============================================================================

@app.get("/api/requests")
def list_requests(
    status_id: int | None = Query(None),
    category_id: int | None = Query(None),
    priority_id: int | None = Query(None),
    room_id: int | None = Query(None),
    requested_by: int | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
) -> list[dict[str, Any]]:
    """List and filter maintenance requests."""
    filters: dict[str, Any] = {"limit": limit, "offset": offset}
    if status_id is not None:
        filters["status_id"] = status_id
    if category_id is not None:
        filters["category_id"] = category_id
    if priority_id is not None:
        filters["priority_id"] = priority_id
    if room_id is not None:
        filters["room_id"] = room_id
    if requested_by is not None:
        filters["requested_by"] = requested_by
    if search:
        filters["search"] = search

    results = request_service.list_requests(filters)
    return serialize_entity(results)


@app.get("/api/requests/{request_id}")
def get_request(request_id: int) -> dict[str, Any]:
    """Retrieve full details of a specific maintenance request."""
    req = request_service.get_request_by_id(request_id)
    return serialize_entity(req)


@app.post("/api/requests", status_code=http_status.HTTP_201_CREATED)
def create_request(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Create a new maintenance request via Phase 3B service."""
    req_date = None
    if payload.get("request_date"):
        req_date = datetime.fromisoformat(payload["request_date"])

    created = request_service.create_request(
        description=payload.get("description", ""),
        category_id=payload.get("category_id"),
        priority_id=payload.get("priority_id"),
        requested_by=payload.get("requested_by"),
        room_id=payload.get("room_id"),
        asset_id=payload.get("asset_id"),
        request_number=payload.get("request_number"),
        request_date=req_date,
        remarks=payload.get("remarks"),
    )
    return serialize_entity(created)


@app.patch("/api/requests/{request_id}")
def update_request(request_id: int, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Update whitelisted attributes on an unclosed maintenance request."""
    updated = request_service.update_request(request_id, payload)
    return serialize_entity(updated)


@app.get("/api/requests/{request_id}/history")
def get_request_history(request_id: int) -> list[dict[str, Any]]:
    """Retrieve chronological audit trail from STATUS_HISTORY."""
    history = request_service.get_status_history(request_id)
    return serialize_entity(history)


@app.post("/api/requests/{request_id}/status")
def change_request_status(request_id: int, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """
    Execute operational status transition (Phase 3E).
    Permitted: Open -> Assigned, Assigned -> In Progress, In Progress <-> On Hold.
    """
    chg_date = None
    if payload.get("changed_date"):
        chg_date = datetime.fromisoformat(payload["changed_date"])

    updated = status_service.change_request_status(
        request_id=request_id,
        new_status=payload.get("new_status"),
        changed_by=payload.get("changed_by"),
        remarks=payload.get("remarks"),
        changed_date=chg_date,
    )
    return serialize_entity(updated)


@app.post("/api/requests/{request_id}/close")
def close_request(request_id: int, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """
    Execute request closure workflow (Phase 3F).
    Permitted only from In Progress or On Hold.
    Requires explicit closed_by, changed_by, closed_date, and resolution_description.
    """
    closed_date = None
    if payload.get("closed_date"):
        closed_date = datetime.fromisoformat(payload["closed_date"])

    closed = closure_service.close_request(
        request_id=request_id,
        closed_by=payload.get("closed_by"),
        resolution_description=payload.get("resolution_description"),
        closed_date=closed_date,
        changed_by=payload.get("changed_by"),
        remarks=payload.get("remarks"),
    )
    return serialize_entity(closed)


@app.get("/api/requests/{request_id}/feedback")
def get_request_feedback(request_id: int) -> dict[str, Any] | None:
    """Retrieve feedback for a closed request (Phase 3G)."""
    fb = feedback_service.get_feedback_for_request(request_id)
    return serialize_entity(fb) if fb else None


@app.post("/api/requests/{request_id}/feedback", status_code=http_status.HTTP_201_CREATED)
def create_request_feedback(request_id: int, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Record customer satisfaction evaluation for a closed request (Phase 3G)."""
    fb_date = None
    if payload.get("feedback_date"):
        fb_date = datetime.fromisoformat(payload["feedback_date"])

    created = feedback_service.create_feedback(
        request_id=request_id,
        user_id=payload.get("user_id"),
        rating=payload.get("rating"),
        comments=payload.get("comments"),
        feedback_date=fb_date,
    )
    return serialize_entity(created)


# =============================================================================
# ASSIGNMENTS & WORK LOGS (Phase 3C)
# =============================================================================

@app.get("/api/assignments")
def list_assignments(
    request_id: int | None = Query(None),
    technician_id: int | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
) -> list[dict[str, Any]]:
    """List technician assignments."""
    filters: dict[str, Any] = {"limit": limit, "offset": offset}
    if request_id is not None:
        filters["request_id"] = request_id
    if technician_id is not None:
        filters["technician_id"] = technician_id
    if status:
        filters["status"] = status

    assignments = assignment_service.list_assignments(filters)
    if assignments:
        assign_ids = [a["assignment_id"] for a in assignments]
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        a.assignment_id,
                        r.description AS description,
                        b.building_name,
                        rm.room_number,
                        p.priority_level
                    FROM assignment a
                    JOIN request r ON a.request_id = r.request_id
                    LEFT JOIN room rm ON r.room_id = rm.room_id
                    LEFT JOIN building b ON rm.building_id = b.building_id
                    LEFT JOIN priority p ON r.priority_id = p.priority_id
                    WHERE a.assignment_id = ANY(%(aids)s);
                """, {"aids": assign_ids})
                meta_by_id = {row["assignment_id"]: row for row in cur.fetchall()}

        for a in assignments:
            if "status" not in a and "assignment_status" in a:
                a["status"] = a["assignment_status"]
            meta = meta_by_id.get(a["assignment_id"])
            if meta:
                if not a.get("description"):
                    a["description"] = meta.get("description")
                a["building_name"] = meta.get("building_name")
                a["room_number"] = meta.get("room_number")
                a["priority_level"] = meta.get("priority_level")
    return serialize_entity(assignments)


@app.get("/api/assignments/{assignment_id}")
def get_assignment(assignment_id: int) -> dict[str, Any]:
    """Retrieve technician assignment by primary key."""
    assignment = assignment_service.get_assignment_by_id(assignment_id)
    if "status" not in assignment and "assignment_status" in assignment:
        assignment["status"] = assignment["assignment_status"]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    r.description AS description,
                    b.building_name,
                    rm.room_number,
                    p.priority_level
                FROM assignment a
                JOIN request r ON a.request_id = r.request_id
                LEFT JOIN room rm ON r.room_id = rm.room_id
                LEFT JOIN building b ON rm.building_id = b.building_id
                LEFT JOIN priority p ON r.priority_id = p.priority_id
                WHERE a.assignment_id = %(aid)s;
            """, {"aid": assignment_id})
            meta = cur.fetchone()
            if meta:
                if not assignment.get("description"):
                    assignment["description"] = meta.get("description")
                assignment["building_name"] = meta.get("building_name")
                assignment["room_number"] = meta.get("room_number")
                assignment["priority_level"] = meta.get("priority_level")
    return serialize_entity(assignment)


@app.post("/api/assignments", status_code=http_status.HTTP_201_CREATED)
def create_assignment(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Create a technician assignment for a request (Phase 3C)."""
    assign_date = datetime.fromisoformat(payload["assigned_date"]) if payload.get("assigned_date") else None
    due_date = datetime.fromisoformat(payload["due_date"]) if payload.get("due_date") else None

    created = assignment_service.create_assignment(
        request_id=payload.get("request_id"),
        technician_id=payload.get("technician_id"),
        assigned_date=assign_date,
        due_date=due_date,
        status=payload.get("status", "Assigned"),
    )
    if "status" not in created and "assignment_status" in created:
        created["status"] = created["assignment_status"]
    return serialize_entity(created)


@app.patch("/api/assignments/{assignment_id}")
def update_assignment(
    assignment_id: int,
    payload: dict[str, Any] = Body(...),
    technician_id: int | None = Query(None),
    x_technician_id: int | None = Header(None, alias="X-Technician-Id"),
) -> dict[str, Any]:
    """Update assignment status or due date (Phase 3C & Phase 4)."""
    # Verify assignment exists first (raises AssignmentNotFoundError / 404 if invalid)
    existing = assignment_service.get_assignment_by_id(assignment_id)

    # Permission check: Technician cannot complete another technician's assignment
    caller_tech_id = payload.get("technician_id") or technician_id or x_technician_id
    if caller_tech_id is not None:
        if int(existing["technician_id"]) != int(caller_tech_id):
            raise ValidationError(
                f"Technician ID {caller_tech_id} is not permitted to modify assignment ID {assignment_id} "
                f"belonging to technician ID {existing['technician_id']}"
            )

    updates = {}
    if "status" in payload:
        updates["status"] = payload["status"]
    if "due_date" in payload and payload["due_date"]:
        updates["due_date"] = datetime.fromisoformat(payload["due_date"])
    if "closed_by" in payload:
        updates["closed_by"] = payload["closed_by"]
    if "resolution_description" in payload:
        updates["resolution_description"] = payload["resolution_description"]

    updated = assignment_service.update_assignment(assignment_id, updates)
    if "status" not in updated and "assignment_status" in updated:
        updated["status"] = updated["assignment_status"]
    return serialize_entity(updated)


@app.get("/api/work-logs")
def list_work_logs(
    assignment_id: int | None = Query(None),
    request_id: int | None = Query(None),
    technician_id: int | None = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
) -> list[dict[str, Any]]:
    """List technician labor work logs (Phase 3C)."""
    filters: dict[str, Any] = {"limit": limit, "offset": offset}
    if assignment_id is not None:
        filters["assignment_id"] = assignment_id
    if request_id is not None:
        filters["request_id"] = request_id
    if technician_id is not None:
        filters["technician_id"] = technician_id

    return serialize_entity(work_log_service.list_work_logs(filters))


@app.post("/api/work-logs", status_code=http_status.HTTP_201_CREATED)
def create_work_log(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Record work log entry with labor hours (Phase 3C)."""
    work_date = datetime.fromisoformat(payload["work_date"]) if payload.get("work_date") else None

    created = work_log_service.create_work_log(
        assignment_id=payload.get("assignment_id"),
        work_description=payload.get("work_description", ""),
        hours_spent=payload.get("hours_spent", 0),
        work_date=work_date,
    )
    return serialize_entity(created)


# =============================================================================
# MATERIALS & COSTS (Phase 3D & Phase 4)
# =============================================================================

@app.get("/api/materials")
def list_materials(search: str | None = Query(None)) -> list[dict[str, Any]]:
    """List inventory materials with current stock levels."""
    filters = {"search": search} if search else None
    return serialize_entity(material_service.list_materials(filters))


@app.post("/api/materials/usage", status_code=http_status.HTTP_201_CREATED)
def record_material_usage(
    payload: dict[str, Any] = Body(...),
    technician_id: int | None = Query(None),
    x_technician_id: int | None = Header(None, alias="X-Technician-Id"),
) -> dict[str, Any]:
    """
    Record material requisition against a work log (Phase 3D & Phase 4).
    Atomically checks stock (FOR UPDATE), decrements stock, inserts WORK_LOG_MATERIAL,
    and inserts single-ledger COST row (CostType='Material') with locked immutable unit price.
    """
    caller_tech_id = payload.get("issued_by") or payload.get("technician_id") or technician_id or x_technician_id
    issued_date = datetime.fromisoformat(payload["issued_date"]) if payload.get("issued_date") else None
    cost_date = datetime.fromisoformat(payload["cost_date"]) if payload.get("cost_date") else None

    if payload.get("material_name") and not payload.get("material_id"):
        usage = material_service.request_material(
            material_name=payload.get("material_name"),
            quantity=payload.get("quantity") or payload.get("quantity_used"),
            unit_price=payload.get("unit_price", 0.0),
            technician_id=int(caller_tech_id) if caller_tech_id else 1,
            assignment_id=payload.get("assignment_id"),
            work_log_id=payload.get("work_log_id"),
        )
        return serialize_entity(usage)

    usage = material_service.record_material_usage(
        work_log_id=payload.get("work_log_id"),
        material_id=payload.get("material_id"),
        quantity_used=payload.get("quantity_used") or payload.get("quantity"),
        issued_by=int(caller_tech_id) if caller_tech_id else payload.get("issued_by"),
        issued_date=issued_date,
        cost_date=cost_date,
        description=payload.get("description"),
        unit_price=payload.get("unit_price"),
    )
    return serialize_entity(usage)


@app.post("/api/technician/material-requests", status_code=http_status.HTTP_201_CREATED)
def create_technician_material_request(
    payload: dict[str, Any] = Body(...),
    technician_id: int | None = Query(None),
    x_technician_id: int | None = Header(None, alias="X-Technician-Id"),
) -> dict[str, Any]:
    """
    Technician portal material requisition endpoint (Phase 4).
    Accepts material name, quantity, unit price, locks the price in single-ledger COST,
    and associates with assignment/work log.
    """
    caller_tech_id = payload.get("technician_id") or technician_id or x_technician_id
    if not caller_tech_id:
        raise ValidationError("technician_id is required")

    usage = material_service.request_material(
        material_name=payload.get("material_name", ""),
        quantity=payload.get("quantity"),
        unit_price=payload.get("unit_price"),
        technician_id=int(caller_tech_id),
        assignment_id=payload.get("assignment_id"),
        work_log_id=payload.get("work_log_id"),
    )
    return serialize_entity(usage)


@app.get("/api/materials/usage")
def list_material_usage(
    technician_id: int | None = Query(None),
    work_log_id: int | None = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
) -> list[dict[str, Any]]:
    """List material usage requisitions with optional filters (Phase 3D)."""
    filters: dict[str, Any] = {"limit": limit, "offset": offset}
    if technician_id is not None:
        filters["technician_id"] = technician_id
    if work_log_id is not None:
        filters["work_log_id"] = work_log_id

    return serialize_entity(material_service.list_material_usage(filters))


@app.get("/api/costs")
def list_costs(
    request_id: int | None = Query(None),
    cost_type: str | None = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
) -> list[dict[str, Any]]:
    """List financial costs recorded in the single COST ledger."""
    filters: dict[str, Any] = {"limit": limit, "offset": offset}
    if request_id is not None:
        filters["request_id"] = request_id
    if cost_type:
        filters["cost_type"] = cost_type

    return serialize_entity(cost_service.list_costs(filters))


# =============================================================================
# REPORTING VIEWS (Locked Phase 2 PostgreSQL Views)
# =============================================================================

@app.get("/api/reports/pending-requests")
def report_pending_requests() -> list[dict[str, Any]]:
    """Authoritative query on locked Phase 2 PostgreSQL view: vw_pending_requests."""
    return serialize_entity(report_repo.get_pending_requests())


@app.get("/api/reports/request-ageing")
def report_request_ageing() -> list[dict[str, Any]]:
    """Authoritative query on locked Phase 2 PostgreSQL view: vw_request_ageing."""
    return serialize_entity(report_repo.get_request_ageing())


@app.get("/api/reports/technician-workload")
def report_technician_workload() -> list[dict[str, Any]]:
    """Authoritative query on locked Phase 2 PostgreSQL view: vw_technician_workload."""
    return serialize_entity(report_repo.get_technician_workload())


@app.get("/api/reports/building-maintenance-cost")
def report_building_maintenance_cost() -> list[dict[str, Any]]:
    """Authoritative query on locked Phase 2 PostgreSQL view: vw_building_maintenance_cost."""
    return serialize_entity(report_repo.get_building_maintenance_cost())


@app.get("/api/reports/material-usage")
def report_material_usage() -> list[dict[str, Any]]:
    """Authoritative query on locked Phase 2 PostgreSQL view: vw_material_usage."""
    return serialize_entity(report_repo.get_material_usage())


@app.get("/api/reports/feedback-summary")
def report_feedback_summary() -> list[dict[str, Any]]:
    """Authoritative query on locked Phase 2 PostgreSQL view: vw_feedback_summary."""
    return serialize_entity(report_repo.get_feedback_summary())


# =============================================================================
# STATIC UI SERVING
# =============================================================================

static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
css_dir = os.path.join(static_dir, "css")
js_dir = os.path.join(static_dir, "js")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir, html=True), name="static")

if os.path.exists(css_dir):
    app.mount("/css", StaticFiles(directory=css_dir), name="css")

if os.path.exists(js_dir):
    app.mount("/js", StaticFiles(directory=js_dir), name="js")


@app.get("/")
@app.head("/")
@app.get("/index.html")
@app.head("/index.html")
def serve_index() -> FileResponse:
    """Serve the Phase 4 Developer Operations Dashboard single-page application."""
    index_path = os.path.join(static_dir, "index.html")
    return FileResponse(index_path, media_type="text/html")


