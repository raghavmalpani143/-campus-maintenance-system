# Review 2 Audit: Campus Maintenance Request ER Diagram
## Campus Facility Maintenance Request Management System (Project #41)

### Executive Summary
This audit provides a formal architectural review of the Review 1 conceptual ER diagram (`screenshots/review1-er.png`) for the Campus Facility Maintenance Request Management System. It details the required corrections and approved structural enhancements needed to achieve Third Normal Form (3NF), maintain strict data integrity, eliminate update anomalies, and support operational and analytical reporting.

The final approved schema consists of **17 normalized relations**, balancing relational rigor with practical operational performance.

---

## 1. Missing Entities & Approved Additions

### 1.1 `STATUS` Lookup Entity (Approved)
* **Issue in Review 1**: `REQUEST.StatusID` and `STATUS_HISTORY.StatusID` were referenced in the schema, but no parent `STATUS` entity existed.
* **Resolution**: Add the `STATUS` master table (`StatusID`, `StatusName`, `Description`).
* **Why Needed**: Provides a controlled domain of allowable request lifecycle stages (e.g., *Open*, *Assigned*, *In Progress*, *On Hold*, *Closed*) and enforces foreign-key referential integrity across the system.

### 1.2 `WORK_LOG_MATERIAL` Associative Entity (Approved)
* **Issue in Review 1**: The relationship between `WORK_LOG` and `MATERIAL` was modeled conceptually as Many-to-Many ($N:M$) without a physical junction table.
* **Resolution**: Create the associative entity `WORK_LOG_MATERIAL` with a composite primary key `(WorkLogID, MaterialID)` and attributes `QuantityUsed`, `IssuedDate`, and `IssuedBy`.
* **Why Needed**: Eliminates repeating groups, enforces 1NF, and guarantees 2NF compliance where quantity and issuance attributes depend strictly on the combination of a specific work log and the material consumed.

### 1.3 `COST` Entity (Approved)
* **Issue in Review 1**: Financial expenditures were not explicitly represented. While raw material unit costs existed in `MATERIAL` and hours existed in `WORK_LOG`, there was no unified ledger to record actual direct costs (service charges, contracted labor, replacement parts, and miscellaneous expenses).
* **Resolution**: Add the `COST` entity (`CostID`, `RequestID`, `CostType`, `Amount`, `CostDate`, `Description`).
* **Why Needed**: Enables direct building-level and request-level financial reporting without double-counting derived calculations or creating ambiguous accounting pipelines.

---

## 2. Relationship & Architectural Reconciliations

### 2.1 Removal of `REQUEST.BuildingID` (3NF Normalization)
* **Issue in Review 1**: `REQUEST` contained both `BuildingID` (FK to `BUILDING`) and `RoomID` (FK to `ROOM`). Because `ROOM` already has a foreign key to `BUILDING`, the functional dependencies are:
  $$\text{RequestID} \rightarrow \text{RoomID}$$
  $$\text{RoomID} \rightarrow \text{BuildingID}$$
  $$\text{Therefore: } \text{RequestID} \rightarrow \text{BuildingID}$$
* **Resolution**: Drop `BuildingID` from `REQUEST`.
* **Why Needed**: Eliminates a classic transitive dependency violation of 3NF. Building information for any request is cleanly and unambiguously derived via `REQUEST → ROOM → BUILDING`.

### 2.2 Correction of `FEEDBACK` Relationships
* **Issue in Review 1**: The diagram showed an erroneous relationship linking `FEEDBACK` to `STATUS_HISTORY`.
* **Resolution**: Ensure `FEEDBACK` relates directly to `REQUEST` (1:0..1 with `RequestID` UNIQUE) and `USER` (N:1 via `UserID`).
* **Why Needed**: Requesters provide satisfaction feedback on the resolved request as a whole and the overall service experience, not on a specific historical status transition event.

### 2.3 Reconciling Technician Specialization (No Additional Tables)
* **Review 1 State**: Technicians have a `Department` attribute (e.g., Electrical, Plumbing, HVAC) in `TECHNICIAN`.
* **Audit Evaluation**: Introducing separate specialization bridge tables (e.g., `TECHNICIAN_CATEGORY` or `TECHNICIAN_SKILL`) was considered during early review, but is **explicitly rejected** in the master project context.
* **Rationale**: The existing `TECHNICIAN.Department` attribute sufficiently categorizes technical staff for university campus operations. Adding specialization junction tables violates the core directive against unnecessary schema expansion beyond the approved 17 tables.

---

## 3. Deliberate Architectural Retentions

### 3.1 Retention of `ASSIGNMENT.Status`
* **Audit Evaluation**: An initial query was raised regarding whether `ASSIGNMENT.Status` duplicates request-level status tracking.
* **Architectural Justification for Retention**:
  * A single maintenance request can involve multiple sequential or parallel technician assignments over its lifecycle.
  * Individual assignments possess their own independent operational states (e.g., *Assigned*, *In Progress*, *Completed*, *Reassigned*, *Cancelled*).
  * *Example*: If Technician A rejects or cannot complete an assignment, that specific `ASSIGNMENT` status is marked *Reassigned* or *Cancelled*, while the overall `REQUEST` status remains *Assigned* or *In Progress* as Technician B takes over.
  * Therefore, `ASSIGNMENT.Status` and `REQUEST.StatusID` govern different lifecycle scopes and must both be retained.

### 3.2 Dual Retention of `REQUEST.StatusID` and `STATUS_HISTORY`
* **Audit Evaluation**: Assessed whether storing current status in `REQUEST.StatusID` alongside historical transitions in `STATUS_HISTORY` constitutes an update anomaly.
* **Architectural Justification for Retention**:
  * `REQUEST.StatusID` represents the **current operational state**. Storing it directly on `REQUEST` allows high-performance filtering, index lookups, and real-time dashboard aggregation without running costly subqueries on historical log tables.
  * `STATUS_HISTORY` represents an **immutable chronological audit log** of every state transition, recording who made the change, when it occurred, and why.
  * This is an intentional and industry-standard operational denormalization.
  * **Consistency Guarantee**: Synchronization is enforced by the **Python backend service layer** via atomic database transactions (`BEGIN ... UPDATE request SET status_id = ...; INSERT INTO status_history ...; COMMIT;`). The database does NOT use triggers for status synchronization or state transition enforcement.

### 3.3 Retention of `MATERIAL.UnitCost`
* **Architectural Justification**: `MATERIAL.UnitCost` is the standard catalog/replacement unit price for an inventory item. It is distinct from the quantity-weighted consumption cost recorded when materials are issued in `WORK_LOG_MATERIAL` or financial expenses logged in `COST`.

---

## 4. Normalization Audit (1NF, 2NF, 3NF)

* **1NF (First Normal Form)**:
  * All attributes are atomic; no comma-separated values, composite strings, or repeating groups.
  * The M:N relationship between `WORK_LOG` and `MATERIAL` is properly decomposed into the associative entity `WORK_LOG_MATERIAL`.
* **2NF (Second Normal Form)**:
  * 16 of the 17 tables utilize single-attribute primary keys (`BIGINT GENERATED ALWAYS AS IDENTITY`), trivially satisfying 2NF.
  * `WORK_LOG_MATERIAL` utilizes the composite primary key `(WorkLogID, MaterialID)`. Non-key attributes (`QuantityUsed`, `IssuedDate`, `IssuedBy`) depend on the full composite key, not on any subset of it.
* **3NF (Third Normal Form)**:
  * Removing `BuildingID` from `REQUEST` resolves the sole transitive dependency identified in the Review 1 design.
  * Every non-prime attribute in every relation is non-transitively dependent on candidate keys.

---

## 5. Constraints and Business Rules Summary

1. **Request Tracking**:
   * `REQUEST.RequestNumber` is enforced `UNIQUE` and human-readable (`REQ-YYYYMMDD-XXXX`).
   * `REQUEST.RoomID` is mandatory; building is derived via `ROOM.BuildingID`.
   * `REQUEST.AssetID` is nullable (requests can target an entire room rather than a specific piece of equipment).
2. **Request Closure Integrity**:
   * When `REQUEST` transitions to *Closed*: `ClosedDate`, `ResolutionDescription`, and `ClosedBy` must be populated.
   * `ClosedDate >= RequestDate`.
3. **Technician & Assignment**:
   * `TECHNICIAN.LaborRate >= 0`.
   * `ASSIGNMENT.DueDate >= ASSIGNMENT.AssignedDate`.
   * Work hours logged in `WORK_LOG.HoursSpent >= 0`.
4. **Material Inventory**:
   * `MATERIAL.StockQty >= 0` and `MATERIAL.UnitCost >= 0`.
   * `WORK_LOG_MATERIAL.QuantityUsed > 0`.
   * Deducting inventory on material usage must occur atomically, preventing negative stock.
5. **Expenditures & Costs**:
   * `COST.Amount >= 0`.
   * `COST.CostType` constrained to approved categories (`'Material'`, `'Labor'`, `'Service'`, `'Miscellaneous'`).
6. **User Feedback**:
   * `FEEDBACK.RequestID` is `UNIQUE` (at most one feedback submission per request).
   * `FEEDBACK.Rating` constrained between 1 and 5.
   * Feedback is accepted only for closed requests (`FeedbackDate >= RequestDate`).

---

## 6. Target Review 2 Schema: 17 Relations

1. `BUILDING`
2. `ROOM`
3. `ASSET`
4. `ROLE`
5. `USER`
6. `CATEGORY`
7. `PRIORITY`
8. `STATUS` *(New lookup)*
9. `TECHNICIAN`
10. `MATERIAL`
11. `REQUEST` *(Normalized: BuildingID removed; Closure fields added)*
12. `ASSIGNMENT` *(Status retained)*
13. `WORK_LOG`
14. `WORK_LOG_MATERIAL` *(New associative entity with composite PK)*
15. `STATUS_HISTORY` *(Synchronized with Request.StatusID)*
16. `COST` *(New expenditure ledger)*
17. `FEEDBACK` *(Direct relation to Request and User)*