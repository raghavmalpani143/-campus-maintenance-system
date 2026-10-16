# System Requirements Specification (SRS)
## Campus Facility Maintenance Request Management System (Project #41)

### Document Overview
This document specifies the functional and non-functional requirements for the **Campus Facility Maintenance Request Management System** (Project #41). The system manages the complete lifecycle of campus maintenance requests across educational buildings, facilities, and physical assets.

---

## 1. System Stakeholders & User Roles

| Role | Description | Core Capabilities |
| :--- | :--- | :--- |
| **Requester** (*Student / Faculty / Staff*) | Campus community members who encounter facility or asset defects. | Submit maintenance requests, view status of submitted requests, provide feedback upon resolution. |
| **Facility Manager / Administrator** | Operations supervisors overseeing campus maintenance. | Triage incoming requests, set priority and category, assign technicians, monitor SLAs, approve request closures, generate reports. |
| **Maintenance Technician** | Skilled internal personnel resolving facility defects. | View assigned jobs, update assignment status, log labor hours, requisition inventory materials, submit resolution summaries. |

---

## 2. Functional Requirements

### FR-1: Request Submission & Identification
* **FR-1.1**: The system shall allow registered users to submit maintenance requests by providing a description, maintenance category, and room location.
* **FR-1.2**: If the defect pertains to a specific piece of equipment, the requester may optionally associate a valid `AssetID` situated in that room.
* **FR-1.3**: The system shall generate a unique, human-readable identifier (`RequestNumber`) formatted as `REQ-YYYYMMDD-XXXX` upon request creation.
* **FR-1.4**: Maintenance requests shall associate with campus buildings exclusively through the `ROOM` entity (`REQUEST → ROOM → BUILDING`), eliminating redundant building attributes on the request.

### FR-2: Request Prioritization & Categorization
* **FR-2.1**: Every request must be classified under a defined `CATEGORY` (e.g., Electrical, Plumbing, HVAC, Carpentry).
* **FR-2.2**: Every request must be assigned a `PRIORITY` level (e.g., Low, Medium, High, Critical) with a defined target response time SLA in hours (`ResponseTimeHr >= 0`).

### FR-3: Technician Work Assignment
* **FR-3.1**: The facility manager shall assign one or more technicians to a request, generating an `ASSIGNMENT` record with an assigned timestamp and optional due date (`DueDate >= AssignedDate`).
* **FR-3.2**: Each `ASSIGNMENT` shall maintain an independent lifecycle status (`'Assigned'`, `'In Progress'`, `'Completed'`, `'Reassigned'`, `'Cancelled'`), distinct from the overarching request status.
* **FR-3.3**: The system shall allow an assignment to be reassigned or cancelled without prematurely closing the parent maintenance request.

### FR-4: Work Execution & Labor Logging
* **FR-4.1**: Technicians shall log daily repair activities via `WORK_LOG` records linked to their specific assignment.
* **FR-4.2**: Each work log entry shall record the date of work, narrative description of tasks completed, and non-negative labor hours spent (`HoursSpent >= 0`).
* **FR-4.3**: Labor costs may be derived based on the logged `HoursSpent` and the technician's hourly `LaborRate`.

### FR-5: Material Inventory & Consumption Tracking
* **FR-5.1**: The system shall maintain an inventory catalog (`MATERIAL`) with item name, unit of measurement, current replacement unit price (`UnitCost >= 0`), and on-hand stock (`StockQty >= 0`).
* **FR-5.2**: When a technician consumes inventory during repairs, a `WORK_LOG_MATERIAL` entry must be created specifying `WorkLogID`, `MaterialID`, quantity consumed (`QuantityUsed > 0`), issuance date, and the issuing technician.
* **FR-5.3**: The system must execute material requisition within an atomic transaction that verifies sufficient stock and automatically decreases `MATERIAL.StockQty`.

### FR-6: Lifecycle State & Audit History
* **FR-6.1**: The system shall enforce a controlled request state progression across five approved statuses:
  $$\text{Open} \longrightarrow \text{Assigned} \longrightarrow \text{In Progress} \longleftrightarrow \text{On Hold} \longrightarrow \text{Closed}$$
  `Closed` is the terminal operational state. Feedback is optional ($1:0..1$) and may be submitted by the requester after closure without altering the closed status.
* **FR-6.2**: The current operational state of a request shall be stored in `REQUEST.StatusID` for fast index queries and operational dashboards.
* **FR-6.3**: Every transition of a request's status must be recorded in `STATUS_HISTORY` with the timestamp, operator (`ChangedBy`), and explanatory remarks.
* **FR-6.4**: Status updates must execute atomically: updating `REQUEST.StatusID` and inserting the corresponding `STATUS_HISTORY` record in the same database transaction.

### FR-7: Request Closure & Resolution Details
* **FR-7.1**: A request cannot be marked *Closed* without recording:
  * The exact closure timestamp (`ClosedDate >= RequestDate`).
  * A detailed narrative of the corrective action taken (`ResolutionDescription`).
  * The identifier of the staff member or manager who authorized the closure (`ClosedBy`).
* **FR-7.2**: While a request is in an open or active status, closure fields must remain `NULL`.

### FR-8: Expenditure Ledger & Cost Management
* **FR-8.1**: The system shall record direct financial expenditures in the `COST` entity, categorized by `CostType` (`'Material'`, `'Labor'`, `'Service'`, `'Miscellaneous'`).
* **FR-8.2**: All cost amounts must be non-negative (`Amount >= 0`).
* **FR-8.3**: Financial queries must aggregate direct recorded costs from `COST` or derived costs from material usage without double-counting.

### FR-9: Requester Satisfaction & Feedback
* **FR-9.1**: Once a request is closed, the original requester may submit an evaluation recorded in `FEEDBACK`.
* **FR-9.2**: The rating score must be an integer between 1 and 5 inclusive (`1 <= Rating <= 5`).
* **FR-9.3**: Each request shall permit at most one feedback record (`FEEDBACK.RequestID` is enforced `UNIQUE`).
* **FR-9.4**: Feedback submissions prior to request creation or closure dates shall be rejected (`FeedbackDate >= RequestDate`).

### FR-10: Analytical & Operational Reporting
The system shall provide the following core reports:
1. **Pending Requests**: Unresolved requests filtered by status, priority, category, and building.
2. **Request Ageing**: Chronological duration analysis showing how long requests remain open against their SLA targets.
3. **Response Time Compliance**: Comparison between actual initial assignment/response time and `PRIORITY.ResponseTimeHr`.
4. **Technician Workload**: Summary of active vs. completed assignments and total accumulated work hours per technician.
5. **Building Maintenance Cost**: Total accumulated maintenance expenditures grouped by building and date range.
6. **Material Consumption**: Breakdown of inventory parts consumed, remaining stock levels, and total material cost per maintenance job.
7. **Requester Feedback Summary**: Average ratings, satisfaction trends, and feedback remarks by building, category, and technician.

---

## 3. Non-Functional Requirements

### NFR-1: Relational Integrity & Data Constraints
* All relations must be normalized to **Third Normal Form (3NF)**.
* Primary keys must utilize PostgreSQL `BIGINT GENERATED ALWAYS AS IDENTITY`.
* Foreign keys must use `BIGINT` (strictly preventing `BIGSERIAL` sequences on foreign keys) and have referential integrity enforced.
* Domain boundaries must be enforced via PostgreSQL `CHECK` constraints (e.g., ratings 1–5, non-negative amounts, non-negative hours, non-negative stock).

### NFR-2: Transactional Integrity & Concurrency
* Multi-step operational state transitions must execute under PostgreSQL `BEGIN ... COMMIT` blocks.
* Transactions must guarantee atomicity: if any step fails (e.g., insufficient material stock), the entire operation must roll back cleanly.

### NFR-3: Performance & Indexing
* Indexes shall be established on high-frequency search and join attributes: `REQUEST(RequestNumber)`, `REQUEST(StatusID)`, `REQUEST(RoomID)`, `ASSIGNMENT(TechnicianID)`, and foreign key columns.

### NFR-4: Application Usability & Fault Tolerance
* The application interface must validate all user inputs prior to submission.
* Database constraint exceptions must be intercepted and rendered as clear, friendly feedback messages rather than raw database stack traces.
