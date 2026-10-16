# Database Normalization Analysis & 3NF Justification
## Campus Facility Maintenance Request Management System (Project #41)

### Executive Overview
This document delivers the formal normalization proof and theoretical justification for the relational database schema of the **Campus Facility Maintenance Request Management System**. Starting from the Review 1 conceptual model, this analysis traces the mathematical decomposition of the schema through **First Normal Form (1NF)**, **Second Normal Form (2NF)**, and **Third Normal Form (3NF)**.

---

## 1. Normalization Theory & Definitions

Let $R(U)$ be a relation schema over attribute set $U$, and let $F$ be the set of functional dependencies holding over $R$.

1. **First Normal Form (1NF)**:
   A relation $R$ is in 1NF if and only if the domain of every attribute contains only atomic (indivisible) values, and there are no repeating groups or multi-valued attributes.
2. **Second Normal Form (2NF)**:
   A relation $R$ is in 2NF if and only if it is in 1NF and every non-prime attribute $A \in (U - K)$ is **fully functionally dependent** on every candidate key $K$. That is, no non-prime attribute is partially dependent on any proper subset of a candidate key:
   $$\forall X \subset K, \; X \not\rightarrow A \quad (\text{where } A \notin K)$$
   *(Note: If a candidate key is a single attribute, partial dependency is mathematically impossible).*
3. **Third Normal Form (3NF)**:
   A relation $R$ is in 3NF if and only if it is in 2NF and for every non-trivial functional dependency $X \rightarrow A \in F^+$, at least one of the following holds:
   - $X$ is a **superkey** of $R$, OR
   - $A$ is a **prime attribute** (i.e., $A$ is a member of some candidate key of $R$).
   Equivalently, no non-prime attribute is transitively dependent on any candidate key of $R$.

---

## 2. Review 1 Evaluation & Identified Anomalies

In the Review 1 conceptual ER design (`screenshots/review1-er.png`), two specific normalization and relational modeling issues were identified:

### Issue A: Many-to-Many Relationship between `WORK_LOG` and `MATERIAL`
* In Review 1, maintenance work execution (`WORK_LOG`) was directly related to inventory (`MATERIAL`) as $N:M$.
* Physical implementation without an associative entity would require storing repeating groups (e.g., arrays or comma-delimited strings of material IDs and quantities within a work log) violating 1NF, or duplicate work log rows violating candidate key uniqueness.

### Issue B: Transitive Dependency in `REQUEST`
* The Review 1 `REQUEST` relation included both `RoomID` and `BuildingID`:
  $$\text{RequestID} \rightarrow \text{RoomID}$$
  $$\text{RoomID} \rightarrow \text{BuildingID}$$
  $$\text{Consequently: } \text{RequestID} \xrightarrow{\text{transitive}} \text{BuildingID}$$
* Here, `BuildingID` is a non-prime attribute functionally determined by `RoomID` (another non-prime attribute), violating the condition that $X$ must be a superkey.
* **Update Anomaly**: If Room 101 is reassigned to another building wing, every past request record for Room 101 would need to be updated. If a request record is updated with an inconsistent building, data corruption occurs.

---

## 3. Step-by-Step Normalization Proof

### 3.1 First Normal Form (1NF) Compliance
To satisfy 1NF:
1. Every attribute domain contains strictly scalar, atomic values (e.g., standard numbers, strings, timestamps, booleans). No multi-valued attributes, JSON arrays, or comma-separated lists are used.
2. The $N:M$ relationship between `WORK_LOG` and `MATERIAL` is decomposed into an explicit associative relation:
   $$\text{WORK\_LOG\_MATERIAL}(\underline{\text{WorkLogID}, \text{MaterialID}}, \text{QuantityUsed}, \text{IssuedDate}, \text{IssuedBy})$$
3. Each record in `WORK_LOG_MATERIAL` represents a single, atomic issuance event of a specific quantity of an inventory item during a specific work log session.

**Conclusion**: All 17 relations satisfy 1NF.

---

### 3.2 Second Normal Form (2NF) Compliance
To satisfy 2NF, no non-prime attribute may depend on a proper subset of any candidate key.

* **Single-Attribute Candidate Key Relations**:
  In 16 of the 17 relations, every candidate key is composed of exactly one attribute:
  * `BUILDING`: $\{BuildingID\}$
  * `ROOM`: $\{RoomID\}$
  * `ASSET`: $\{AssetID\}$
  * `ROLE`: $\{RoleID\}$, $\{RoleName\}$
  * `USER`: $\{UserID\}$, $\{Email\}$
  * `CATEGORY`: $\{CategoryID\}$
  * `PRIORITY`: $\{PriorityID\}$, $\{PriorityLevel\}$
  * `STATUS`: $\{StatusID\}$, $\{StatusName\}$
  * `TECHNICIAN`: $\{TechnicianID\}$
  * `MATERIAL`: $\{MaterialID\}$
  * `REQUEST`: $\{RequestID\}$, $\{RequestNumber\}$
  * `ASSIGNMENT`: $\{AssignmentID\}$
  * `WORK_LOG`: $\{WorkLogID\}$
  * `STATUS_HISTORY`: $\{StatusHistoryID\}$
  * `COST`: $\{CostID\}$
  * `FEEDBACK`: $\{FeedbackID\}$, $\{RequestID\}$

  *Proof*: Because $|K| = 1$ for all candidate keys in these 16 relations, there are no proper non-empty subsets of $K$. Therefore, partial dependencies cannot exist.

* **Composite Candidate Key Relation (`WORK_LOG_MATERIAL`)**:
  * Primary Key: $K = \{\text{WorkLogID}, \text{MaterialID}\}$
  * Non-prime attributes: $\text{QuantityUsed}, \text{IssuedDate}, \text{IssuedBy}$
  * Functional Dependency:
    $$\{\text{WorkLogID}, \text{MaterialID}\} \rightarrow \text{QuantityUsed}, \text{IssuedDate}, \text{IssuedBy}$$
  * *Proof of Full Functional Dependency*:
    - $\text{WorkLogID} \not\rightarrow \text{QuantityUsed}$: A single work log session may involve multiple distinct materials; knowing only the work log does not determine the quantity of any particular material.
    - $\text{MaterialID} \not\rightarrow \text{QuantityUsed}$: A given material is used across dozens of different work logs in different quantities; knowing the material ID does not determine how much was used in a specific repair.
    - Thus, $\text{QuantityUsed}$ depends on the **entire composite key** $\{\text{WorkLogID}, \text{MaterialID}\}$.
    - The same logic applies to $\text{IssuedDate}$ and $\text{IssuedBy}$ for that requisition event.

**Conclusion**: All 17 relations satisfy 2NF.

---

### 3.3 Third Normal Form (3NF) Compliance
To satisfy 3NF, for every functional dependency $X \rightarrow A$, either $X$ is a superkey, or $A$ is a prime attribute.

#### A. Resolution of the Transitive Dependency in `REQUEST`
In Review 1:
$$\text{REQUEST}(\text{RequestID}, \dots, \text{RoomID}, \text{BuildingID}, \dots)$$
$$\text{RequestID} \rightarrow \text{RoomID}, \quad \text{RoomID} \rightarrow \text{BuildingID}$$
Since $\text{RoomID}$ is not a superkey in `REQUEST`, this violated 3NF.

**Review 2 Decomposition**:
Remove `BuildingID` from `REQUEST`. The relations become:
$$\text{ROOM}(\underline{\text{RoomID}}, \text{RoomNumber}, \text{RoomType}, \text{Floor}, \text{BuildingID})$$
$$\text{REQUEST}(\underline{\text{RequestID}}, \text{RequestNumber}, \text{RequestDate}, \text{Description}, \text{CategoryID}, \text{PriorityID}, \text{RequestedBy}, \text{RoomID}, \text{AssetID}, \text{StatusID}, \dots)$$

In the decomposed schema:
1. In `ROOM`, $\text{RoomID} \rightarrow \text{BuildingID}$ holds, and $\{\text{RoomID}\}$ is a superkey of `ROOM`.
2. In `REQUEST`, `BuildingID` no longer exists. The relationship between a request and its physical building is reconstituted lossless-ly via the relational join:
   $$\text{REQUEST} \bowtie \text{ROOM} \bowtie \text{BUILDING}$$

#### B. Verification of Non-Transitivity Across Other Relations
* **`TECHNICIAN(TechnicianID, ..., LaborRate)`**:
  $\text{TechnicianID} \rightarrow \text{LaborRate}$ is a direct dependency. Labor rate is an individual contractual rate. It is not determined by Department or any other non-prime attribute.
* **`MATERIAL(MaterialID, ..., UnitCost, StockQty)`**:
  $\text{MaterialID} \rightarrow \text{UnitCost}$ represents the standard replacement catalog unit price of that specific inventory stock item. Unit does not determine UnitCost.
* **`ASSIGNMENT(AssignmentID, RequestID, TechnicianID, AssignedDate, DueDate, Status)`**:
  $\text{AssignmentID} \rightarrow \text{Status}$ represents the state of that technician's individual assignment. It is not functionally determined by $\text{RequestID}$ (which has its own status).
* **`FEEDBACK(FeedbackID, RequestID, UserID, Rating, Comments, FeedbackDate)`**:
  Since $\text{RequestID}$ is unique, both $\{\text{FeedbackID}\}$ and $\{\text{RequestID}\}$ are candidate keys. Thus, every dependency has a superkey on its left-hand side.
* **`COST(CostID, RequestID, CostType, Amount, CostDate, Description)`**:
  $\text{CostID}$ is a surrogate primary key and superkey. All cost attributes depend directly on $\text{CostID}$.

---

## 4. Intentional Operational State vs. Normalization

A common question in database evaluation is whether maintaining both `REQUEST.StatusID` and `STATUS_HISTORY` constitutes a normalization violation:

* `REQUEST.StatusID` represents the **current state snapshot** of the entity.
* `STATUS_HISTORY` represents a **discrete event log** of historical state transitions:
  $$\text{STATUS\_HISTORY}(\underline{\text{StatusHistoryID}}, \text{RequestID}, \text{StatusID}, \text{ChangedBy}, \text{ChangedDate}, \text{Remarks})$$
* This separation is an **intentional, standard operational pattern** rather than a 3NF redundancy:
  1. `REQUEST.StatusID` provides instant $O(1)$ query capability for dashboard filtering (e.g., active requests) without requiring expensive aggregation over millions of audit log records.
  2. Data consistency is formally maintained by wrapping state modifications in **atomic database transactions** (updating `REQUEST.StatusID` and inserting the corresponding `STATUS_HISTORY` tuple within the same `BEGIN ... COMMIT` block).

---

## 5. Formal Normalization Matrix

| # | Entity Name | Primary Key | Alternate / Candidate Keys | 1NF | 2NF | 3NF | Justification Summary |
| :-: | :--- | :--- | :--- | :-: | :-: | :-: | :--- |
| 1 | `BUILDING` | `BuildingID` | — | ✓ | ✓ | ✓ | Atomic attributes, single-column PK, all FDs emanate from PK. |
| 2 | `ROOM` | `RoomID` | `{BuildingID, RoomNumber}` | ✓ | ✓ | ✓ | Single-column PK, non-prime attributes directly dependent on key. |
| 3 | `ASSET` | `AssetID` | — | ✓ | ✓ | ✓ | Direct dependency on AssetID; RoomID is direct FK. |
| 4 | `ROLE` | `RoleID` | `RoleName` | ✓ | ✓ | ✓ | Lookup table with unique name candidate key. |
| 5 | `USER` | `UserID` | `Email` | ✓ | ✓ | ✓ | Both UserID and Email are candidate keys. |
| 6 | `CATEGORY` | `CategoryID` | — | ✓ | ✓ | ✓ | Single-column PK, atomic attributes. |
| 7 | `PRIORITY` | `PriorityID` | `PriorityLevel` | ✓ | ✓ | ✓ | Lookup table; ResponseTimeHr depends on priority identity. |
| 8 | `STATUS` | `StatusID` | `StatusName` | ✓ | ✓ | ✓ | Lookup table; StatusName candidate key. |
| 9 | `TECHNICIAN` | `TechnicianID` | — | ✓ | ✓ | ✓ | Single-column PK; LaborRate depends on TechnicianID. |
| 10 | `MATERIAL` | `MaterialID` | — | ✓ | ✓ | ✓ | Single-column PK; catalog unit cost depends on MaterialID. |
| 11 | `REQUEST` | `RequestID` | `RequestNumber` | ✓ | ✓ | ✓ | 3NF achieved by removing BuildingID; closure fields dependent on PK. |
| 12 | `ASSIGNMENT` | `AssignmentID` | — | ✓ | ✓ | ✓ | Single-column PK; assignment status tracks worker assignment lifecycle. |
| 13 | `WORK_LOG` | `WorkLogID` | — | ✓ | ✓ | ✓ | Single-column PK; work narrative and hours depend on WorkLogID. |
| 14 | `WORK_LOG_MATERIAL` | `(WorkLogID, MaterialID)`| — | ✓ | ✓ | ✓ | Composite PK; QuantityUsed and issuance attributes depend on full PK. |
| 15 | `STATUS_HISTORY` | `StatusHistoryID` | — | ✓ | ✓ | ✓ | Single-column PK; audit trail of state changes. |
| 16 | `COST` | `CostID` | — | ✓ | ✓ | ✓ | Single-column PK; direct expenditure ledger records. |
| 17 | `FEEDBACK` | `FeedbackID` | `RequestID` | ✓ | ✓ | ✓ | 1:0..1 evaluation record; RequestID enforced UNIQUE. |

**Final Conclusion**: The finalized Review 2 relational schema of 17 tables rigorously satisfies **Third Normal Form (3NF)**.
