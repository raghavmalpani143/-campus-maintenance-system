# Functional Dependencies Analysis — Review 2 Final Design
## Campus Facility Maintenance Request Management System (Project #41)

This document provides a formal functional dependency (FD) analysis for all 17 entities in the finalized Review 2 design of the Campus Facility Maintenance Request Management System. It incorporates the approved normalization corrections (resolving the Review 1 3NF violation, adding the `STATUS` lookup, resolving the M:N material relationship via `WORK_LOG_MATERIAL`, and adding `COST`).

---

## 1. Functional Dependencies by Relation

### 1.1 BUILDING
* **Attributes**: `BuildingID`, `BuildingName`, `Location`, `Description`
* **Candidate Key(s)**: `{BuildingID}`
* **Primary Key**: `BuildingID`
* **Functional Dependencies**:
  * `BuildingID → BuildingName, Location, Description`
* **Analysis**: `BuildingID` uniquely identifies the building. All non-key attributes are fully dependent on the primary key.

---

### 1.2 ROOM
* **Attributes**: `RoomID`, `RoomNumber`, `RoomType`, `Floor`, `BuildingID`
* **Candidate Key(s)**: `{RoomID}`, `{BuildingID, RoomNumber}` (a room number is unique within a specific building)
* **Primary Key**: `RoomID`
* **Foreign Key**: `BuildingID → BUILDING(BuildingID)`
* **Functional Dependencies**:
  * `RoomID → RoomNumber, RoomType, Floor, BuildingID`
  * `{BuildingID, RoomNumber} → RoomID, RoomType, Floor`
* **Analysis**: Every non-key attribute depends directly on `RoomID`.

---

### 1.3 ASSET
* **Attributes**: `AssetID`, `AssetName`, `AssetType`, `Brand/Model`, `InstallDate`, `RoomID`, `Status`
* **Candidate Key(s)**: `{AssetID}`
* **Primary Key**: `AssetID`
* **Foreign Key**: `RoomID → ROOM(RoomID)`
* **Functional Dependencies**:
  * `AssetID → AssetName, AssetType, Brand/Model, InstallDate, RoomID, Status`
* **Analysis**: All descriptive and operational attributes are functionally determined by `AssetID`.

---

### 1.4 ROLE
* **Attributes**: `RoleID`, `RoleName`, `Description`
* **Candidate Key(s)**: `{RoleID}`, `{RoleName}` (RoleName is unique)
* **Primary Key**: `RoleID`
* **Functional Dependencies**:
  * `RoleID → RoleName, Description`
  * `RoleName → RoleID, Description`
* **Analysis**: Single-attribute candidate keys; in 3NF.

---

### 1.5 USER
* **Attributes**: `UserID`, `FullName`, `Email`, `Phone`, `RoleID`, `Status`
* **Candidate Key(s)**: `{UserID}`, `{Email}` (Email is enforced UNIQUE)
* **Primary Key**: `UserID`
* **Foreign Key**: `RoleID → ROLE(RoleID)`
* **Functional Dependencies**:
  * `UserID → FullName, Email, Phone, RoleID, Status`
  * `Email → UserID, FullName, Phone, RoleID, Status`
* **Analysis**: Both `UserID` and `Email` are superkeys. All non-prime attributes are directly dependent on candidate keys.

---

### 1.6 CATEGORY
* **Attributes**: `CategoryID`, `CategoryName`, `Description`
* **Candidate Key(s)**: `{CategoryID}`
* **Primary Key**: `CategoryID`
* **Functional Dependencies**:
  * `CategoryID → CategoryName, Description`
* **Analysis**: All descriptive attributes depend directly on `CategoryID`.

---

### 1.7 PRIORITY
* **Attributes**: `PriorityID`, `PriorityLevel`, `Description`, `ResponseTimeHr`
* **Candidate Key(s)**: `{PriorityID}`, `{PriorityLevel}`
* **Primary Key**: `PriorityID`
* **Functional Dependencies**:
  * `PriorityID → PriorityLevel, Description, ResponseTimeHr`
  * `PriorityLevel → PriorityID, Description, ResponseTimeHr`
* **Analysis**: In 3NF/BCNF.

---

### 1.8 STATUS (Review 2 Added Entity)
* **Attributes**: `StatusID`, `StatusName`, `Description`
* **Candidate Key(s)**: `{StatusID}`, `{StatusName}`
* **Primary Key**: `StatusID`
* **Functional Dependencies**:
  * `StatusID → StatusName, Description`
  * `StatusName → StatusID, Description`
* **Analysis**: Controlled lookup relation; no transitive or partial dependencies.

---

### 1.9 TECHNICIAN
* **Attributes**: `TechnicianID`, `FullName`, `Phone`, `Email`, `Department`, `Status`, `LaborRate`
* **Candidate Key(s)**: `{TechnicianID}`
* **Primary Key**: `TechnicianID`
* **Functional Dependencies**:
  * `TechnicianID → FullName, Phone, Email, Department, Status, LaborRate`
* **Analysis**: `LaborRate` directly depends on `TechnicianID` (standard individual labor rate).

---

### 1.10 MATERIAL
* **Attributes**: `MaterialID`, `MaterialName`, `Unit`, `UnitCost`, `StockQty`, `Status`
* **Candidate Key(s)**: `{MaterialID}`
* **Primary Key**: `MaterialID`
* **Functional Dependencies**:
  * `MaterialID → MaterialName, Unit, UnitCost, StockQty, Status`
* **Analysis**: `UnitCost` is the standard replacement/catalog unit cost, depending directly on `MaterialID`.

---

### 1.11 REQUEST
* **Attributes**: `RequestID`, `RequestNumber`, `RequestDate`, `Description`, `CategoryID`, `PriorityID`, `RequestedBy`, `RoomID`, `AssetID`, `StatusID`, `ClosedDate`, `ResolutionDescription`, `ClosedBy`
* **Candidate Key(s)**: `{RequestID}`, `{RequestNumber}` (enforced UNIQUE)
* **Primary Key**: `RequestID`
* **Foreign Keys**:
  * `CategoryID → CATEGORY(CategoryID)`
  * `PriorityID → PRIORITY(PriorityID)`
  * `RequestedBy → USER(UserID)`
  * `RoomID → ROOM(RoomID)`
  * `AssetID → ASSET(AssetID)` (nullable)
  * `StatusID → STATUS(StatusID)`
  * `ClosedBy → USER(UserID)` (nullable)
* **Functional Dependencies**:
  * `RequestID → RequestNumber, RequestDate, Description, CategoryID, PriorityID, RequestedBy, RoomID, AssetID, StatusID, ClosedDate, ResolutionDescription, ClosedBy`
  * `RequestNumber → RequestID, RequestDate, Description, CategoryID, PriorityID, RequestedBy, RoomID, AssetID, StatusID, ClosedDate, ResolutionDescription, ClosedBy`
* **Review 2 Normalization Correction**:
  * *Review 1 Violation*: `RequestID → RoomID` and `RoomID → BuildingID` caused transitive dependency `RequestID → BuildingID`.
  * *Correction*: `BuildingID` was removed from `REQUEST`. Building is now referenced exclusively via `RoomID → ROOM.BuildingID`.
  * *Closure Attributes*: Closure attributes (`ClosedDate`, `ResolutionDescription`, `ClosedBy`) are functionally dependent on `RequestID`.

---

### 1.12 ASSIGNMENT
* **Attributes**: `AssignmentID`, `RequestID`, `TechnicianID`, `AssignedDate`, `DueDate`, `Status`
* **Candidate Key(s)**: `{AssignmentID}`
* **Primary Key**: `AssignmentID`
* **Foreign Keys**:
  * `RequestID → REQUEST(RequestID)`
  * `TechnicianID → TECHNICIAN(TechnicianID)`
* **Functional Dependencies**:
  * `AssignmentID → RequestID, TechnicianID, AssignedDate, DueDate, Status`
* **Analysis**: `ASSIGNMENT.Status` represents the specific operational lifecycle of that technician's assignment (e.g., 'Assigned', 'In Progress', 'Completed', 'Cancelled'), distinct from the overall `REQUEST.StatusID`.

---

### 1.13 WORK_LOG
* **Attributes**: `WorkLogID`, `AssignmentID`, `WorkDate`, `WorkDescription`, `HoursSpent`
* **Candidate Key(s)**: `{WorkLogID}`
* **Primary Key**: `WorkLogID`
* **Foreign Key**: `AssignmentID → ASSIGNMENT(AssignmentID)`
* **Functional Dependencies**:
  * `WorkLogID → AssignmentID, WorkDate, WorkDescription, HoursSpent`
* **Analysis**: Work log entries depend strictly on `AssignmentID`; no direct `RequestID` or `TechnicianID` attributes exist, preventing redundancy.

---

### 1.14 WORK_LOG_MATERIAL (Review 2 Junction Entity)
* **Attributes**: `WorkLogID`, `MaterialID`, `QuantityUsed`, `IssuedDate`, `IssuedBy`
* **Candidate Key(s)**: `{(WorkLogID, MaterialID)}`
* **Primary Key**: Composite `(WorkLogID, MaterialID)`
* **Foreign Keys**:
  * `WorkLogID → WORK_LOG(WorkLogID)`
  * `MaterialID → MATERIAL(MaterialID)`
  * `IssuedBy → TECHNICIAN(TechnicianID)`
* **Functional Dependencies**:
  * `(WorkLogID, MaterialID) → QuantityUsed, IssuedDate, IssuedBy`
* **Analysis**: 
  * Neither `WorkLogID` nor `MaterialID` alone can determine `QuantityUsed`, `IssuedDate`, or `IssuedBy`.
  * All non-key attributes are fully functionally dependent on the entire composite primary key `(WorkLogID, MaterialID)`, satisfying 2NF.
  * No surrogate key is required.

---

### 1.15 STATUS_HISTORY
* **Attributes**: `StatusHistoryID`, `RequestID`, `StatusID`, `ChangedBy`, `ChangedDate`, `Remarks`
* **Candidate Key(s)**: `{StatusHistoryID}`
* **Primary Key**: `StatusHistoryID`
* **Foreign Keys**:
  * `RequestID → REQUEST(RequestID)`
  * `StatusID → STATUS(StatusID)`
  * `ChangedBy → USER(UserID)`
* **Functional Dependencies**:
  * `StatusHistoryID → RequestID, StatusID, ChangedBy, ChangedDate, Remarks`
* **Analysis**: Represents an append-only audit trail. Each entry records an atomic state change event.

---

### 1.16 COST (Review 2 Added Entity)
* **Attributes**: `CostID`, `RequestID`, `CostType`, `Amount`, `CostDate`, `Description`
* **Candidate Key(s)**: `{CostID}`
* **Primary Key**: `CostID`
* **Foreign Key**: `RequestID → REQUEST(RequestID)`
* **Functional Dependencies**:
  * `CostID → RequestID, CostType, Amount, CostDate, Description`
* **Analysis**: Tracks recorded financial expenses directly attributable to a maintenance request. All non-key attributes depend directly on `CostID`.

---

### 1.17 FEEDBACK
* **Attributes**: `FeedbackID`, `RequestID`, `UserID`, `Rating`, `Comments`, `FeedbackDate`
* **Candidate Key(s)**: `{FeedbackID}`, `{RequestID}` (one feedback per request constraint)
* **Primary Key**: `FeedbackID`
* **Foreign Keys**:
  * `RequestID → REQUEST(RequestID)` (UNIQUE)
  * `UserID → USER(UserID)`
* **Functional Dependencies**:
  * `FeedbackID → RequestID, UserID, Rating, Comments, FeedbackDate`
  * `RequestID → FeedbackID, UserID, Rating, Comments, FeedbackDate`
* **Analysis**: Because `{RequestID}` is unique, it is a candidate key. All attributes are directly dependent on the candidate keys. Links directly to `REQUEST` and `USER` (removing the invalid Review 1 link to `STATUS_HISTORY`).

---

## 2. Normalization Summary Across All 17 Tables

| Relation | Primary Key | Highest Normal Form | Justification |
| :--- | :--- | :---: | :--- |
| `BUILDING` | `BuildingID` | 3NF / BCNF | Single-column PK, all non-key attributes fully & directly dependent on PK. |
| `ROOM` | `RoomID` | 3NF / BCNF | Single-column PK, no transitive dependencies within relation. |
| `ASSET` | `AssetID` | 3NF / BCNF | Single-column PK, room association is a direct FK. |
| `ROLE` | `RoleID` | 3NF / BCNF | Single-column PK, `RoleName` is an alternate key. |
| `USER` | `UserID` | 3NF / BCNF | `UserID` and `Email` are candidate keys; no transitive dependencies. |
| `CATEGORY` | `CategoryID` | 3NF / BCNF | Single-column PK, atomic attributes. |
| `PRIORITY` | `PriorityID` | 3NF / BCNF | Single-column PK, `PriorityLevel` is an alternate key. |
| `STATUS` | `StatusID` | 3NF / BCNF | Single-column PK, `StatusName` is an alternate key. |
| `TECHNICIAN` | `TechnicianID` | 3NF / BCNF | Single-column PK, labor rate directly determined by technician identity. |
| `MATERIAL` | `MaterialID` | 3NF / BCNF | Single-column PK, standard unit price directly determined by material identity. |
| `REQUEST` | `RequestID` | 3NF / BCNF | `BuildingID` removed, eliminating transitive dependency (`RequestID → RoomID → BuildingID`). |
| `ASSIGNMENT` | `AssignmentID` | 3NF / BCNF | Assignment status belongs strictly to assignment lifecycle. |
| `WORK_LOG` | `WorkLogID` | 3NF / BCNF | Single-column PK, depends strictly on `AssignmentID`. |
| `WORK_LOG_MATERIAL` | `(WorkLogID, MaterialID)` | 3NF / BCNF | Composite PK, no partial dependencies, no transitive dependencies. |
| `STATUS_HISTORY` | `StatusHistoryID` | 3NF / BCNF | Single-column PK, immutable chronological log entries. |
| `COST` | `CostID` | 3NF / BCNF | Single-column PK, tracks individual cost ledger items per request. |
| `FEEDBACK` | `FeedbackID` | 3NF / BCNF | `RequestID` is unique candidate key; evaluated request is direct. |