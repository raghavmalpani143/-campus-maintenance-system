# Relational Schema Specification — Review 2 Final Design
## Campus Facility Maintenance Request Management System (Project #41)

This document specifies the finalized relational schema for the **Campus Facility Maintenance Request Management System**. It outlines the schema notation, attribute definitions, referential integrities, cardinalities, and relationship topologies for all 17 approved tables.

---

## 1. Formal Relational Schema Notation

In the notation below:
- **`PK`** indicates a Primary Key component (underlined).
- **`FK`** indicates a Foreign Key reference.
- **`UQ`** indicates an alternate key / Unique constraint.

```text
1.  BUILDING (
        BuildingID [PK], BuildingName, Location, Description
    )

2.  ROOM (
        RoomID [PK], RoomNumber, RoomType, Floor,
        BuildingID [FK → BUILDING.BuildingID]
    )

3.  ASSET (
        AssetID [PK], AssetName, AssetType, Brand/Model, InstallDate, Status,
        RoomID [FK → ROOM.RoomID]
    )

4.  ROLE (
        RoleID [PK], RoleName [UQ], Description
    )

5.  USER (
        UserID [PK], FullName, Email [UQ], Phone, Status,
        RoleID [FK → ROLE.RoleID]
    )

6.  CATEGORY (
        CategoryID [PK], CategoryName, Description
    )

7.  PRIORITY (
        PriorityID [PK], PriorityLevel [UQ], Description, ResponseTimeHr
    )

8.  STATUS (
        StatusID [PK], StatusName [UQ], Description
    )

9.  TECHNICIAN (
        TechnicianID [PK], FullName, Phone, Email, Department, Status, LaborRate
    )

10. MATERIAL (
        MaterialID [PK], MaterialName, Unit, UnitCost, StockQty, Status
    )

11. REQUEST (
        RequestID [PK], RequestNumber [UQ], RequestDate, Description,
        CategoryID [FK → CATEGORY.CategoryID],
        PriorityID [FK → PRIORITY.PriorityID],
        RequestedBy [FK → USER.UserID],
        RoomID [FK → ROOM.RoomID],
        AssetID [FK → ASSET.AssetID, Nullable],
        StatusID [FK → STATUS.StatusID],
        ClosedDate, ResolutionDescription,
        ClosedBy [FK → USER.UserID, Nullable]
    )

12. ASSIGNMENT (
        AssignmentID [PK], AssignedDate, DueDate, Status,
        RequestID [FK → REQUEST.RequestID],
        TechnicianID [FK → TECHNICIAN.TechnicianID]
    )

13. WORK_LOG (
        WorkLogID [PK], WorkDate, WorkDescription, HoursSpent,
        AssignmentID [FK → ASSIGNMENT.AssignmentID]
    )

14. WORK_LOG_MATERIAL (
        WorkLogID [PK, FK → WORK_LOG.WorkLogID],
        MaterialID [PK, FK → MATERIAL.MaterialID],
        QuantityUsed, IssuedDate,
        IssuedBy [FK → TECHNICIAN.TechnicianID]
    )

15. STATUS_HISTORY (
        StatusHistoryID [PK], ChangedDate, Remarks,
        RequestID [FK → REQUEST.RequestID],
        StatusID [FK → STATUS.StatusID],
        ChangedBy [FK → USER.UserID]
    )

16. COST (
        CostID [PK], CostType, Amount, CostDate, Description,
        RequestID [FK → REQUEST.RequestID]
    )

17. FEEDBACK (
        FeedbackID [PK], Rating, Comments, FeedbackDate,
        RequestID [UQ, FK → REQUEST.RequestID],
        UserID [FK → USER.UserID]
    )
```

---

## 2. Table Relationship Topology & Cardinalities

```
[BUILDING] 1 ────────── N [ROOM] 1 ────────── N [ASSET]
                             │
                             │ 1
                             │
                             │ N
[CATEGORY] 1 ─────────┐      │
[PRIORITY] 1 ─────────┼──────┼──────── N [REQUEST] 1 ─── 0..1 [FEEDBACK]
[STATUS]   1 ─────────┼──────┘             │   │                   │
[USER]     1 (ReqBy) ─┘                    │   │                   │
[USER]     1 (ClosedBy) ───────────────────┘   │                   │
[USER]     1 ──────────────────────────────────┼───────────────────┘
                                               │
                                               ├────── 1:N ────── [STATUS_HISTORY]
                                               │
                                               ├────── 1:N ────── [COST]
                                               │
                                               └────── 1:N ────── [ASSIGNMENT]
                                                                        │
                                   [TECHNICIAN] 1 ──────────────────────┤ (N:1)
                                                                        │
                                                                        ▼ (1:N)
                                                                    [WORK_LOG]
                                                                        │
                                                                        ▼ (1:N)
                                   [MATERIAL]   1 ──────── N [WORK_LOG_MATERIAL]
                                   [TECHNICIAN] 1 ──────── N (IssuedBy)
```

### Cardinality Specifications
1. **BUILDING to ROOM**: One-to-Many ($1:N$). A building contains 1 or more rooms; a room belongs to exactly 1 building.
2. **ROOM to ASSET**: One-to-Many ($1:N$). A room may contain 0 or more assets; an asset is housed in exactly 1 room.
3. **ROLE to USER**: One-to-Many ($1:N$). A role is assigned to 0 or more users; a user has exactly 1 role.
4. **CATEGORY to REQUEST**: One-to-Many ($1:N$). A category classifies 0 or more requests; a request has exactly 1 category.
5. **PRIORITY to REQUEST**: One-to-Many ($1:N$). A priority level applies to 0 or more requests; a request has exactly 1 priority.
6. **STATUS to REQUEST**: One-to-Many ($1:N$). A status state is associated with 0 or more requests; a request has exactly 1 current status.
7. **ROOM to REQUEST**: One-to-Many ($1:N$). A room may be the site of 0 or more maintenance requests; a request originates in exactly 1 room.
8. **ASSET to REQUEST**: Optional One-to-Many ($0..1:N$). An asset may be the subject of 0 or more requests; a request may optionally reference 0 or 1 asset.
9. **USER to REQUEST (RequestedBy)**: One-to-Many ($1:N$). A user may submit 0 or more requests; a request is submitted by exactly 1 user.
10. **USER to REQUEST (ClosedBy)**: Optional One-to-Many ($0..1:N$). An authorized user may close 0 or more requests; a closed request is closed by at most 1 user.
11. **REQUEST to ASSIGNMENT**: One-to-Many ($1:N$). A request can have 1 or more technician assignments; an assignment references exactly 1 request.
12. **TECHNICIAN to ASSIGNMENT**: One-to-Many ($1:N$). A technician can be assigned 0 or more requests; an assignment designates exactly 1 technician.
13. **ASSIGNMENT to WORK_LOG**: One-to-Many ($1:N$). An assignment can accumulate 0 or more work log entries; a work log belongs to exactly 1 assignment.
14. **WORK_LOG to WORK_LOG_MATERIAL**: One-to-Many ($1:N$). A work log can record the consumption of 0 or more inventory materials; each entry is tied to that work log.
15. **MATERIAL to WORK_LOG_MATERIAL**: One-to-Many ($1:N$). A material item can be consumed across 0 or more work logs; each entry references exactly 1 material.
16. **TECHNICIAN to WORK_LOG_MATERIAL (IssuedBy)**: One-to-Many ($1:N$). A technician can issue materials for 0 or more records; each requisition record references 1 issuing technician.
17. **REQUEST to STATUS_HISTORY**: One-to-Many ($1:N$). A request accumulates 1 or more historical status records over its lifecycle; each entry belongs to exactly 1 request.
18. **STATUS to STATUS_HISTORY**: One-to-Many ($1:N$). A status state appears in 0 or more historical transition logs.
19. **USER to STATUS_HISTORY (ChangedBy)**: One-to-Many ($1:N$). A user/admin may record 0 or more status changes.
20. **REQUEST to COST**: One-to-Many ($1:N$). A request may accrue 0 or more direct expense ledger entries; each cost entry belongs to exactly 1 request.
21. **REQUEST to FEEDBACK**: One-to-Optional-One ($1:0..1$). A closed request can receive at most 1 feedback evaluation (`RequestID` is `UNIQUE`); a feedback entry evaluates exactly 1 request.
22. **USER to FEEDBACK**: One-to-Many ($1:N$). A user can submit feedback on 0 or more requests they submitted.

---

## 3. Comprehensive Constraints Matrix

| Constraint Category | Target Relation | Constrained Attribute(s) | Rule / Expression |
| :--- | :--- | :--- | :--- |
| **PRIMARY KEY** | `BUILDING` | `BuildingID` | `PRIMARY KEY (BuildingID)` |
| | `ROOM` | `RoomID` | `PRIMARY KEY (RoomID)` |
| | `ASSET` | `AssetID` | `PRIMARY KEY (AssetID)` |
| | `ROLE` | `RoleID` | `PRIMARY KEY (RoleID)` |
| | `USER` | `UserID` | `PRIMARY KEY (UserID)` |
| | `CATEGORY` | `CategoryID` | `PRIMARY KEY (CategoryID)` |
| | `PRIORITY` | `PriorityID` | `PRIMARY KEY (PriorityID)` |
| | `STATUS` | `StatusID` | `PRIMARY KEY (StatusID)` |
| | `TECHNICIAN` | `TechnicianID` | `PRIMARY KEY (TechnicianID)` |
| | `MATERIAL` | `MaterialID` | `PRIMARY KEY (MaterialID)` |
| | `REQUEST` | `RequestID` | `PRIMARY KEY (RequestID)` |
| | `ASSIGNMENT` | `AssignmentID` | `PRIMARY KEY (AssignmentID)` |
| | `WORK_LOG` | `WorkLogID` | `PRIMARY KEY (WorkLogID)` |
| | `WORK_LOG_MATERIAL` | `(WorkLogID, MaterialID)` | `PRIMARY KEY (WorkLogID, MaterialID)` |
| | `STATUS_HISTORY` | `StatusHistoryID` | `PRIMARY KEY (StatusHistoryID)` |
| | `COST` | `CostID` | `PRIMARY KEY (CostID)` |
| | `FEEDBACK` | `FeedbackID` | `PRIMARY KEY (FeedbackID)` |
| **UNIQUE** | `ROLE` | `RoleName` | `UNIQUE (RoleName)` |
| | `USER` | `Email` | `UNIQUE (Email)` |
| | `PRIORITY` | `PriorityLevel` | `UNIQUE (PriorityLevel)` |
| | `STATUS` | `StatusName` | `UNIQUE (StatusName)` |
| | `REQUEST` | `RequestNumber` | `UNIQUE (RequestNumber)` |
| | `FEEDBACK` | `RequestID` | `UNIQUE (RequestID)` (enforces $1:0..1$) |
| **CHECK** | `ROOM` | `Floor` | `Floor >= 0` |
| | `PRIORITY` | `ResponseTimeHr` | `ResponseTimeHr >= 0` |
| | `PRIORITY` | `PriorityLevel` | `PriorityLevel IN ('Low', 'Medium', 'High', 'Critical')` |
| | `TECHNICIAN` | `LaborRate` | `LaborRate >= 0` |
| | `MATERIAL` | `UnitCost` | `UnitCost >= 0` |
| | `MATERIAL` | `StockQty` | `StockQty >= 0` |
| | `WORK_LOG` | `HoursSpent` | `HoursSpent >= 0` |
| | `WORK_LOG_MATERIAL`| `QuantityUsed` | `QuantityUsed > 0` |
| | `COST` | `Amount` | `Amount >= 0` |
| | `COST` | `CostType` | `CostType IN ('Material', 'Labor', 'Service', 'Miscellaneous')` |
| | `FEEDBACK` | `Rating` | `Rating >= 1 AND Rating <= 5` |
| | `REQUEST` | `ClosedDate` | `ClosedDate IS NULL OR ClosedDate >= RequestDate` |
| | `ASSIGNMENT` | `DueDate` | `DueDate IS NULL OR DueDate >= AssignedDate` |

---

## 4. Evolution from Review 1 to Final Review 2 Schema

| Aspect | Review 1 Conceptual ER | Review 2 Final Relational Schema | Reason / Impact |
| :--- | :--- | :--- | :--- |
| **Total Tables** | 13 conceptual entities | **17 normalized relations** | Full relational implementation, normalization, and cost tracking. |
| **Request Building** | `REQUEST.BuildingID` + `RoomID` | `REQUEST.RoomID` only | Eliminates 3NF transitive dependency; building resolved via `ROOM`. |
| **Status Master** | Missing; `StatusID` had no parent | `STATUS` entity added | Enforces referential integrity on valid status lifecycle stages. |
| **Work Log Materials** | Direct $N:M$ without junction table | `WORK_LOG_MATERIAL` junction with composite PK `(WorkLogID, MaterialID)` | Eliminates repeating groups, enforces 1NF and 2NF. |
| **Cost Ledger** | Missing direct cost entity | `COST` entity added | Provides unified accounting ledger for material, labor, and external charges. |
| **Request Closure** | Missing closure attributes | `ClosedDate`, `ResolutionDescription`, `ClosedBy` added to `REQUEST` | Captures closure audit details and resolution summaries. |
| **Feedback Link** | Erroneously linked to `STATUS_HISTORY` | Linked directly to `REQUEST` and `USER` | Requesters evaluate the completed request, not a history transition log. |
| **Assignment State**| `ASSIGNMENT.Status` present | `ASSIGNMENT.Status` retained | Supports independent worker assignment lifecycles within a request. |
| **Current vs History**| `REQUEST.StatusID` & `STATUS_HISTORY`| Both retained (atomic transaction sync) | Optimized operational querying coupled with immutable audit logging. |
