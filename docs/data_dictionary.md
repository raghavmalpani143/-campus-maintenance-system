# Data Dictionary — Review 2 Final Logical Design
## Campus Facility Maintenance Request Management System (Project #41)

This document defines the comprehensive data dictionary for all 17 approved entities in the Campus Facility Maintenance Request Management System. It reflects the finalized Review 2 logical design conforming to Third Normal Form (3NF), PostgreSQL data typing standards, and the authoritative project master context.

---

### Data Typing & Identity Standards
- **Surrogate Primary Keys**: `BIGINT GENERATED ALWAYS AS IDENTITY` (PostgreSQL standard SQL:2008 identity column).
- **Foreign Keys**: `BIGINT` referencing the corresponding parent entity's primary key (strictly avoiding `BIGSERIAL` on foreign keys).
- **Composite Primary Keys**: Applied directly on junction entities (`WORK_LOG_MATERIAL`) to prevent unnecessary surrogate keys and uphold 2NF.
- **Monetary / Quantities / Hours**: `NUMERIC` with explicit precision and scale to prevent floating-point rounding errors.
- **Temporal Data**: `TIMESTAMP` (or `DATE` for calendar dates).

---

## 1. BUILDING

Stores campus building master records.

| Attribute Name | Data Type | Size/Precision | Constraints / Keys | Nullable | Default | Validation / Business Rule | Description / Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `BuildingID` | BIGINT | Identity | PK | NOT NULL | Generated Always | Positive integer | Unique identifier for the building |
| `BuildingName` | VARCHAR | 100 | — | NOT NULL | — | Non-empty string | Official name of the campus building |
| `Location` | VARCHAR | 200 | — | NOT NULL | — | Non-empty string | Campus zone, quadrant, or physical address |
| `Description` | TEXT | — | — | NULL | — | — | Additional details, landmarks, or notes |

*Changes from Review 1*: None (unchanged).

---

## 2. ROOM

Stores specific rooms and spaces within campus buildings.

| Attribute Name | Data Type | Size/Precision | Constraints / Keys | Nullable | Default | Validation / Business Rule | Description / Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `RoomID` | BIGINT | Identity | PK | NOT NULL | Generated Always | Positive integer | Unique identifier for the room |
| `RoomNumber` | VARCHAR | 20 | — | NOT NULL | — | Non-empty string | Room number/code (e.g., '101', 'LAB-3') |
| `RoomType` | VARCHAR | 50 | — | NOT NULL | — | — | Type of room (e.g., Classroom, Lab, Office, Washroom) |
| `Floor` | INTEGER | — | — | NOT NULL | — | `Floor >= 0` | Floor level (0 = Ground Floor) |
| `BuildingID` | BIGINT | — | FK → BUILDING(`BuildingID`) | NOT NULL | — | Must reference valid building | Parent building housing this room |

*Changes from Review 1*: None (unchanged).

---

## 3. ASSET

Stores physical equipment and fixed assets installed in campus rooms.

| Attribute Name | Data Type | Size/Precision | Constraints / Keys | Nullable | Default | Validation / Business Rule | Description / Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `AssetID` | BIGINT | Identity | PK | NOT NULL | Generated Always | Positive integer | Unique identifier for the asset |
| `AssetName` | VARCHAR | 100 | — | NOT NULL | — | Non-empty string | Asset name (e.g., 'Split AC 1.5 Ton', 'Ceiling Projector') |
| `AssetType` | VARCHAR | 50 | — | NOT NULL | — | — | Category/Type (e.g., HVAC, Electrical, Plumbing, IT) |
| `Brand/Model` | VARCHAR | 100 | — | NOT NULL | — | — | Manufacturer brand and model number |
| `InstallDate` | DATE | — | — | NOT NULL | — | `InstallDate <= CURRENT_DATE` | Date asset was commissioned/installed |
| `RoomID` | BIGINT | — | FK → ROOM(`RoomID`) | NOT NULL | — | Must reference valid room | Room where the asset is located |
| `Status` | VARCHAR | 20 | — | NOT NULL | 'Active' | `Status IN ('Active', 'Under Maintenance', 'Decommissioned')` | Current operational state of the asset |

*Changes from Review 1*: None (unchanged).

---

## 4. ROLE

Stores user authorization and system access roles.

| Attribute Name | Data Type | Size/Precision | Constraints / Keys | Nullable | Default | Validation / Business Rule | Description / Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `RoleID` | BIGINT | Identity | PK | NOT NULL | Generated Always | Positive integer | Unique identifier for the role |
| `RoleName` | VARCHAR | 50 | UNIQUE | NOT NULL | — | Non-empty string | Name of the role (e.g., 'Student', 'Faculty', 'Staff', 'Facility Manager') |
| `Description` | TEXT | — | — | NULL | — | — | Scope of permissions and responsibilities |

*Changes from Review 1*: None (unchanged).

---

## 5. USER

Stores campus community members who submit requests, approve closures, or provide feedback.

| Attribute Name | Data Type | Size/Precision | Constraints / Keys | Nullable | Default | Validation / Business Rule | Description / Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `UserID` | BIGINT | Identity | PK | NOT NULL | Generated Always | Positive integer | Unique identifier for the user |
| `FullName` | VARCHAR | 100 | — | NOT NULL | — | Non-empty string | Full legal name of the user |
| `Email` | VARCHAR | 255 | UNIQUE | NOT NULL | — | Valid email format | Official campus email address |
| `Phone` | VARCHAR | 20 | — | NULL | — | Phone format | Contact phone number |
| `RoleID` | BIGINT | — | FK → ROLE(`RoleID`) | NOT NULL | — | Must reference valid role | Access role assigned to this user |
| `Status` | VARCHAR | 20 | — | NOT NULL | 'Active' | `Status IN ('Active', 'Inactive', 'Suspended')` | User account status |

*Changes from Review 1*: None (unchanged).

---

## 6. CATEGORY

Stores maintenance service domains.

| Attribute Name | Data Type | Size/Precision | Constraints / Keys | Nullable | Default | Validation / Business Rule | Description / Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `CategoryID` | BIGINT | Identity | PK | NOT NULL | Generated Always | Positive integer | Unique identifier for the category |
| `CategoryName` | VARCHAR | 100 | — | NOT NULL | — | Non-empty string | Category title (e.g., 'Electrical', 'Plumbing', 'HVAC', 'Carpentry') |
| `Description` | TEXT | — | — | NULL | — | — | Description of issues covered by this category |

*Changes from Review 1*: None (unchanged).

---

## 7. PRIORITY

Stores maintenance priority classifications and service level agreements (SLAs).

| Attribute Name | Data Type | Size/Precision | Constraints / Keys | Nullable | Default | Validation / Business Rule | Description / Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `PriorityID` | BIGINT | Identity | PK | NOT NULL | Generated Always | Positive integer | Unique identifier for the priority level |
| `PriorityLevel` | VARCHAR | 20 | — | NOT NULL | — | `PriorityLevel IN ('Low', 'Medium', 'High', 'Critical')` | Priority classification name |
| `Description` | TEXT | — | — | NULL | — | — | Criteria for assigning this priority level |
| `ResponseTimeHr` | INTEGER | — | — | NOT NULL | — | `ResponseTimeHr >= 0` | Target SLA response time in hours |

*Changes from Review 1*: None (unchanged).

---

## 8. STATUS (Approved Review 2 Entity)

Master lookup entity for controlled request and status history lifecycle states.

| Attribute Name | Data Type | Size/Precision | Constraints / Keys | Nullable | Default | Validation / Business Rule | Description / Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `StatusID` | BIGINT | Identity | PK | NOT NULL | Generated Always | Positive integer | Unique identifier for the status |
| `StatusName` | VARCHAR | 50 | UNIQUE | NOT NULL | — | Controlled vocabulary | Name of status (e.g., 'Open', 'Assigned', 'In Progress', 'On Hold', 'Closed') |
| `Description` | TEXT | — | — | NULL | — | — | Explanation of what this status state represents |

*Changes from Review 1*: **Added**. Eliminates referential integrity gaps in Review 1 where `REQUEST.StatusID` and `STATUS_HISTORY.StatusID` lacked a parent entity.

---

## 9. TECHNICIAN

Stores internal maintenance technicians executing work assignments.

| Attribute Name | Data Type | Size/Precision | Constraints / Keys | Nullable | Default | Validation / Business Rule | Description / Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `TechnicianID` | BIGINT | Identity | PK | NOT NULL | Generated Always | Positive integer | Unique identifier for the technician |
| `FullName` | VARCHAR | 100 | — | NOT NULL | — | Non-empty string | Full name of the technician |
| `Phone` | VARCHAR | 20 | — | NULL | — | Phone format | Direct contact telephone number |
| `Email` | VARCHAR | 255 | — | NULL | — | Valid email format | Contact email address |
| `Department` | VARCHAR | 100 | — | NOT NULL | — | Non-empty string | Maintenance division (e.g., 'Electrical Maintenance', 'Civil Works') |
| `Status` | VARCHAR | 20 | — | NOT NULL | 'Active' | `Status IN ('Active', 'Inactive', 'On Leave')` | Operational availability status |
| `LaborRate` | NUMERIC | 10,2 | — | NOT NULL | 0.00 | `LaborRate >= 0` | Standard hourly labor billing rate (in ₹) |

*Changes from Review 1*:
- **Added**: `LaborRate` attribute to support direct labor cost reporting without inventing unnecessary salary or rate-card entities.

---

## 10. MATERIAL

Stores campus spare parts and maintenance inventory items.

| Attribute Name | Data Type | Size/Precision | Constraints / Keys | Nullable | Default | Validation / Business Rule | Description / Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `MaterialID` | BIGINT | Identity | PK | NOT NULL | Generated Always | Positive integer | Unique identifier for the material item |
| `MaterialName` | VARCHAR | 100 | — | NOT NULL | — | Non-empty string | Item description (e.g., 'LED Tube Light 20W', 'PVC Elbow 1/2"') |
| `Unit` | VARCHAR | 20 | — | NOT NULL | — | Non-empty string | Unit of measurement (e.g., 'Piece', 'Meter', 'Kg', 'Box') |
| `UnitCost` | NUMERIC | 10,2 | — | NOT NULL | — | `UnitCost >= 0` | Standard replacement cost per unit (in ₹) |
| `StockQty` | INTEGER | — | — | NOT NULL | 0 | `StockQty >= 0` | Quantity currently in stock |
| `Status` | VARCHAR | 20 | — | NOT NULL | 'Active' | `Status IN ('Active', 'Discontinued', 'Out of Stock')` | Inventory catalog status |

*Changes from Review 1*: None (unchanged). `UnitCost` is intentionally retained as the catalog unit price, separate from actual material issuance costs.

---

## 11. REQUEST

Core entity tracking maintenance service requests from submission to resolution.

| Attribute Name | Data Type | Size/Precision | Constraints / Keys | Nullable | Default | Validation / Business Rule | Description / Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `RequestID` | BIGINT | Identity | PK | NOT NULL | Generated Always | Positive integer | Unique internal surrogate identifier |
| `RequestNumber` | VARCHAR | 30 | UNIQUE | NOT NULL | — | Format: `REQ-YYYYMMDD-XXXX` | Human-readable unique tracking number |
| `RequestDate` | TIMESTAMP | — | — | NOT NULL | CURRENT_TIMESTAMP | `RequestDate <= CURRENT_TIMESTAMP` | Date and time the request was submitted |
| `Description` | TEXT | — | — | NOT NULL | — | Non-empty text | Detailed description of the maintenance issue |
| `CategoryID` | BIGINT | — | FK → CATEGORY(`CategoryID`) | NOT NULL | — | Valid CategoryID | Issue domain category |
| `PriorityID` | BIGINT | — | FK → PRIORITY(`PriorityID`) | NOT NULL | — | Valid PriorityID | Assigned priority and response SLA |
| `RequestedBy` | BIGINT | — | FK → USER(`UserID`) | NOT NULL | — | Valid UserID | Requester submitting the maintenance issue |
| `RoomID` | BIGINT | — | FK → ROOM(`RoomID`) | NOT NULL | — | Valid RoomID | Room where the issue is physically located |
| `AssetID` | BIGINT | — | FK → ASSET(`AssetID`) | NULL | — | Valid AssetID or NULL | Specific asset needing service (NULL if room-level issue) |
| `StatusID` | BIGINT | — | FK → STATUS(`StatusID`) | NOT NULL | — | Valid StatusID | Current operational state of the request |
| `ClosedDate` | TIMESTAMP | — | — | NULL | — | `ClosedDate IS NULL OR ClosedDate >= RequestDate` | Timestamp when request was closed |
| `ResolutionDescription` | TEXT | — | — | NULL | — | Required when Closed | Summary of repair actions taken |
| `ClosedBy` | BIGINT | — | FK → USER(`UserID`) | NULL | — | Valid UserID or NULL | User/Staff member who authorized closure |

*Changes from Review 1*:
- **Removed**: `BuildingID` (deliberate 3NF normalization; building is transitively derived via `RoomID → BuildingID`).
- **Added**: `ClosedDate`, `ResolutionDescription`, `ClosedBy` (to capture closure lifecycle details).

---

## 12. ASSIGNMENT

Tracks individual technician work allocations for a request.

| Attribute Name | Data Type | Size/Precision | Constraints / Keys | Nullable | Default | Validation / Business Rule | Description / Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `AssignmentID` | BIGINT | Identity | PK | NOT NULL | Generated Always | Positive integer | Unique identifier for the assignment record |
| `RequestID` | BIGINT | — | FK → REQUEST(`RequestID`) | NOT NULL | — | Valid RequestID | Request being serviced |
| `TechnicianID` | BIGINT | — | FK → TECHNICIAN(`TechnicianID`) | NOT NULL | — | Valid TechnicianID | Technician assigned to perform work |
| `AssignedDate` | TIMESTAMP | — | — | NOT NULL | CURRENT_TIMESTAMP | — | Timestamp assignment was issued |
| `DueDate` | TIMESTAMP | — | — | NULL | — | `DueDate IS NULL OR DueDate >= AssignedDate` | Target completion deadline |
| `Status` | VARCHAR | 20 | — | NOT NULL | 'Assigned' | `Status IN ('Assigned', 'In Progress', 'Completed', 'Reassigned', 'Cancelled')` | Status of this specific technician assignment |

*Changes from Review 1*: None (unchanged).
*Note*: `ASSIGNMENT.Status` is deliberately retained because an individual assignment has its own lifecycle independent of the overall request status (e.g., when an assignment is reassigned or cancelled, but the request remains open).

---

## 13. WORK_LOG

Records labor hours and work execution details by assigned technicians.

| Attribute Name | Data Type | Size/Precision | Constraints / Keys | Nullable | Default | Validation / Business Rule | Description / Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `WorkLogID` | BIGINT | Identity | PK | NOT NULL | Generated Always | Positive integer | Unique identifier for the work log entry |
| `AssignmentID` | BIGINT | — | FK → ASSIGNMENT(`AssignmentID`) | NOT NULL | — | Valid AssignmentID | Parent assignment under which work was done |
| `WorkDate` | TIMESTAMP | — | — | NOT NULL | CURRENT_TIMESTAMP | `WorkDate <= CURRENT_TIMESTAMP` | Date and time when the work was executed |
| `WorkDescription` | TEXT | — | — | NOT NULL | — | Non-empty text | Narrative of actions performed |
| `HoursSpent` | NUMERIC | 5,2 | — | NOT NULL | — | `HoursSpent >= 0` | Time spent on the job in hours |

*Changes from Review 1*: None (unchanged). Does not contain direct `RequestID` or `TechnicianID` columns because both are naturally resolved through `ASSIGNMENT`.

---

## 14. WORK_LOG_MATERIAL (Approved Review 2 Associative Entity)

Resolves the N:M relationship between work logs and materials; tracks exact materials consumed.

| Attribute Name | Data Type | Size/Precision | Constraints / Keys | Nullable | Default | Validation / Business Rule | Description / Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `WorkLogID` | BIGINT | — | PK, FK → WORK_LOG(`WorkLogID`) | NOT NULL | — | Valid WorkLogID | Work log during which material was consumed |
| `MaterialID` | BIGINT | — | PK, FK → MATERIAL(`MaterialID`) | NOT NULL | — | Valid MaterialID | Material inventory item issued |
| `QuantityUsed` | NUMERIC | 8,2 | — | NOT NULL | — | `QuantityUsed > 0` | Quantity consumed (in Material.Unit) |
| `IssuedDate` | TIMESTAMP | — | — | NOT NULL | CURRENT_TIMESTAMP | — | Date/time material was checked out |
| `IssuedBy` | BIGINT | — | FK → TECHNICIAN(`TechnicianID`) | NOT NULL | — | Valid TechnicianID | Technician who requisitioned the material |

*Primary Key*: `PRIMARY KEY (WorkLogID, MaterialID)` (composite primary key enforcing 2NF; avoids redundant surrogate key).  
*Changes from Review 1*: **Added**. Resolves the Review 1 N:M conceptual relationship.

---

## 15. STATUS_HISTORY

Maintains an immutable historical audit log of all request status transitions.

| Attribute Name | Data Type | Size/Precision | Constraints / Keys | Nullable | Default | Validation / Business Rule | Description / Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `StatusHistoryID` | BIGINT | Identity | PK | NOT NULL | Generated Always | Positive integer | Unique audit record identifier |
| `RequestID` | BIGINT | — | FK → REQUEST(`RequestID`) | NOT NULL | — | Valid RequestID | Request whose status changed |
| `StatusID` | BIGINT | — | FK → STATUS(`StatusID`) | NOT NULL | — | Valid StatusID | Status state transitioned into |
| `ChangedBy` | BIGINT | — | FK → USER(`UserID`) | NOT NULL | — | Valid UserID | User or administrator executing the transition |
| `ChangedDate` | TIMESTAMP | — | — | NOT NULL | CURRENT_TIMESTAMP | — | Timestamp when transition was recorded |
| `Remarks` | TEXT | — | — | NULL | — | — | Operational notes or reason for status change |

*Changes from Review 1*: None (unchanged). References new `STATUS` entity.

---

## 16. COST (Approved Review 2 Entity)

Tracks all financial expenditures and accounting records associated with a maintenance request.

| Attribute Name | Data Type | Size/Precision | Constraints / Keys | Nullable | Default | Validation / Business Rule | Description / Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `CostID` | BIGINT | Identity | PK | NOT NULL | Generated Always | Positive integer | Unique identifier for the cost entry |
| `RequestID` | BIGINT | — | FK → REQUEST(`RequestID`) | NOT NULL | — | Valid RequestID | Request incurring this expenditure |
| `CostType` | VARCHAR | 30 | — | NOT NULL | — | `CostType IN ('Material', 'Labor', 'Service', 'Miscellaneous')` | Expenditure category classification |
| `Amount` | NUMERIC | 10,2 | — | NOT NULL | — | `Amount >= 0` | Incurred cost amount (in ₹) |
| `CostDate` | TIMESTAMP | — | — | NOT NULL | CURRENT_TIMESTAMP | — | Date/time cost was logged or incurred |
| `Description` | TEXT | — | — | NULL | — | — | Justification or invoice details |

*Changes from Review 1*: **Added**. Directly satisfies the requirement for building-level and request-level financial reporting without ambiguous double-counting.

---

## 17. FEEDBACK

Stores requester satisfaction evaluations submitted following request completion.

| Attribute Name | Data Type | Size/Precision | Constraints / Keys | Nullable | Default | Validation / Business Rule | Description / Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `FeedbackID` | BIGINT | Identity | PK | NOT NULL | Generated Always | Positive integer | Unique identifier for feedback submission |
| `RequestID` | BIGINT | — | FK → REQUEST(`RequestID`), UNIQUE | NOT NULL | — | One feedback per request | Serviced request being evaluated |
| `UserID` | BIGINT | — | FK → USER(`UserID`) | NOT NULL | — | Valid UserID | User providing the evaluation |
| `Rating` | INTEGER | — | — | NOT NULL | — | `Rating >= 1 AND Rating <= 5` | Satisfaction rating (1 = Poor, 5 = Excellent) |
| `Comments` | TEXT | — | — | NULL | — | — | Qualitative remarks from requester |
| `FeedbackDate` | TIMESTAMP | — | — | NOT NULL | CURRENT_TIMESTAMP | `FeedbackDate >= RequestDate` | Date and time feedback was submitted |

*Changes from Review 1*: None (unchanged). Corrected relationship links directly to `REQUEST` and `USER` (removing the erroneous Review 1 link to `STATUS_HISTORY`).

---

## Summary of Normalized Architecture (17 Tables)

```
Campus Infrastructure:
  BUILDING (1) ──< ROOM (2) ──< ASSET (3)

Access & People:
  ROLE (4) ──< USER (5)
  TECHNICIAN (9)

Classifications & State:
  CATEGORY (6)
  PRIORITY (7)
  STATUS (8)

Operational Core:
  REQUEST (11) ──< ASSIGNMENT (12) ──< WORK_LOG (13) ──< WORK_LOG_MATERIAL (14) >── MATERIAL (10)
     ├──< STATUS_HISTORY (15)
     ├──< COST (16)
     └─── FEEDBACK (17)
```