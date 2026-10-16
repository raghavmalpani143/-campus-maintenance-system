-- ============================================================================
-- CAMPUS FACILITY MAINTENANCE REQUEST MANAGEMENT SYSTEM (Project #41)
-- File: 01_schema.sql
-- Description: Core DDL definitions for the 17 approved normalized relations.
-- Standards: PostgreSQL 14+, standard identity columns, BIGINT foreign keys.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. BUILDING
-- Stores campus building master records.
-- ----------------------------------------------------------------------------
CREATE TABLE building (
    building_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    building_name   VARCHAR(100) NOT NULL,
    location        VARCHAR(200) NOT NULL,
    description     TEXT
);

-- ----------------------------------------------------------------------------
-- 2. ROOM
-- Stores specific rooms and physical locations within campus buildings.
-- ----------------------------------------------------------------------------
CREATE TABLE room (
    room_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    room_number     VARCHAR(20) NOT NULL,
    room_type       VARCHAR(50) NOT NULL,
    floor           INTEGER NOT NULL,
    building_id     BIGINT NOT NULL
);

-- ----------------------------------------------------------------------------
-- 3. ASSET
-- Stores physical equipment and fixed assets installed in campus rooms.
-- Note: 'brand_model' maps to Review 1 'Brand/Model' attribute.
-- ----------------------------------------------------------------------------
CREATE TABLE asset (
    asset_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asset_name      VARCHAR(100) NOT NULL,
    asset_type      VARCHAR(50) NOT NULL,
    brand_model     VARCHAR(100) NOT NULL,
    install_date    DATE NOT NULL,
    room_id         BIGINT NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'Active'
);

-- ----------------------------------------------------------------------------
-- 4. ROLE
-- Stores user authorization and access roles.
-- ----------------------------------------------------------------------------
CREATE TABLE role (
    role_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role_name       VARCHAR(50) NOT NULL,
    description     TEXT
);

-- ----------------------------------------------------------------------------
-- 5. USER
-- Stores campus community members (students, faculty, staff, administrators).
-- Note: Quoted identifier "user" is used as 'user' is a SQL reserved keyword.
-- ----------------------------------------------------------------------------
CREATE TABLE "user" (
    user_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name       VARCHAR(100) NOT NULL,
    email           VARCHAR(255) NOT NULL,
    phone           VARCHAR(20),
    role_id         BIGINT NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'Active'
);

-- ----------------------------------------------------------------------------
-- 6. CATEGORY
-- Stores maintenance service domains.
-- ----------------------------------------------------------------------------
CREATE TABLE category (
    category_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category_name   VARCHAR(100) NOT NULL,
    description     TEXT
);

-- ----------------------------------------------------------------------------
-- 7. PRIORITY
-- Stores maintenance priority levels and target response time SLAs in hours.
-- ----------------------------------------------------------------------------
CREATE TABLE priority (
    priority_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    priority_level   VARCHAR(20) NOT NULL,
    description      TEXT,
    response_time_hr INTEGER NOT NULL
);

-- ----------------------------------------------------------------------------
-- 8. STATUS
-- Controlled lookup entity for request and status-history lifecycle states.
-- ----------------------------------------------------------------------------
CREATE TABLE status (
    status_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    status_name     VARCHAR(50) NOT NULL,
    description     TEXT
);

-- ----------------------------------------------------------------------------
-- 9. TECHNICIAN
-- Stores technical staff executing maintenance assignments.
-- ----------------------------------------------------------------------------
CREATE TABLE technician (
    technician_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name       VARCHAR(100) NOT NULL,
    phone           VARCHAR(20),
    email           VARCHAR(255),
    department      VARCHAR(100) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'Active',
    labor_rate      NUMERIC(10, 2) NOT NULL DEFAULT 0.00
);

-- ----------------------------------------------------------------------------
-- 10. MATERIAL
-- Stores maintenance inventory items, stock levels, and standard unit costs.
-- ----------------------------------------------------------------------------
CREATE TABLE material (
    material_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    material_name   VARCHAR(100) NOT NULL,
    unit            VARCHAR(20) NOT NULL,
    unit_cost       NUMERIC(10, 2) NOT NULL,
    stock_qty       INTEGER NOT NULL DEFAULT 0,
    status          VARCHAR(20) NOT NULL DEFAULT 'Active'
);

-- ----------------------------------------------------------------------------
-- 11. REQUEST
-- Core entity tracking facility maintenance service requests.
-- Note: BuildingID is deliberately excluded in 3NF (derived via room_id).
-- ----------------------------------------------------------------------------
CREATE TABLE request (
    request_id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_number          VARCHAR(30) NOT NULL,
    request_date            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description             TEXT NOT NULL,
    category_id             BIGINT NOT NULL,
    priority_id             BIGINT NOT NULL,
    requested_by            BIGINT NOT NULL,
    room_id                 BIGINT NOT NULL,
    asset_id                BIGINT,
    status_id               BIGINT NOT NULL,
    closed_date             TIMESTAMP,
    resolution_description  TEXT,
    closed_by               BIGINT
);

-- ----------------------------------------------------------------------------
-- 12. ASSIGNMENT
-- Tracks individual technician allocations for a request.
-- Note: ASSIGNMENT.status is retained as assignments have independent lifecycles.
-- ----------------------------------------------------------------------------
CREATE TABLE assignment (
    assignment_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id      BIGINT NOT NULL,
    technician_id   BIGINT NOT NULL,
    assigned_date   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    due_date        TIMESTAMP,
    status          VARCHAR(20) NOT NULL DEFAULT 'Assigned'
);

-- ----------------------------------------------------------------------------
-- 13. WORK_LOG
-- Records labor hours and work execution details under an assignment.
-- Note: Does not contain direct request_id or technician_id columns.
-- ----------------------------------------------------------------------------
CREATE TABLE work_log (
    work_log_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    assignment_id    BIGINT NOT NULL,
    work_date        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    work_description TEXT NOT NULL,
    hours_spent      NUMERIC(5, 2) NOT NULL
);

-- ----------------------------------------------------------------------------
-- 14. WORK_LOG_MATERIAL
-- Associative entity resolving N:M relationship between work logs and materials.
-- Uses composite primary key (work_log_id, material_id) to strictly uphold 2NF.
-- ----------------------------------------------------------------------------
CREATE TABLE work_log_material (
    work_log_id     BIGINT NOT NULL,
    material_id     BIGINT NOT NULL,
    quantity_used   NUMERIC(8, 2) NOT NULL,
    issued_date     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    issued_by       BIGINT NOT NULL,
    PRIMARY KEY (work_log_id, material_id)
);

-- ----------------------------------------------------------------------------
-- 15. STATUS_HISTORY
-- Immutable chronological audit trail of request status transitions.
-- ----------------------------------------------------------------------------
CREATE TABLE status_history (
    status_history_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id        BIGINT NOT NULL,
    status_id         BIGINT NOT NULL,
    changed_by        BIGINT NOT NULL,
    changed_date      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    remarks           TEXT
);

-- ----------------------------------------------------------------------------
-- 16. COST
-- Single recorded-cost ledger for direct maintenance expenditures.
-- ----------------------------------------------------------------------------
CREATE TABLE cost (
    cost_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id      BIGINT NOT NULL,
    cost_type       VARCHAR(30) NOT NULL,
    amount          NUMERIC(10, 2) NOT NULL,
    cost_date       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description     TEXT
);

-- ----------------------------------------------------------------------------
-- 17. FEEDBACK
-- Stores requester satisfaction evaluations upon request closure.
-- ----------------------------------------------------------------------------
CREATE TABLE feedback (
    feedback_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id      BIGINT NOT NULL,
    user_id         BIGINT NOT NULL,
    rating          INTEGER NOT NULL,
    comments        TEXT,
    feedback_date   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
