-- ============================================================================
-- CAMPUS FACILITY MAINTENANCE REQUEST MANAGEMENT SYSTEM (Project #41)
-- File: 02_constraints.sql
-- Description: Foreign Keys, Unique Constraints, Check Constraints, and Triggers.
-- ============================================================================

-- ============================================================================
-- 1. FOREIGN KEY CONSTRAINTS
-- ============================================================================

-- ROOM references BUILDING
ALTER TABLE room
    ADD CONSTRAINT fk_room_building
    FOREIGN KEY (building_id) REFERENCES building (building_id)
    ON DELETE RESTRICT;

-- ASSET references ROOM
ALTER TABLE asset
    ADD CONSTRAINT fk_asset_room
    FOREIGN KEY (room_id) REFERENCES room (room_id)
    ON DELETE RESTRICT;

-- USER references ROLE
ALTER TABLE "user"
    ADD CONSTRAINT fk_user_role
    FOREIGN KEY (role_id) REFERENCES role (role_id)
    ON DELETE RESTRICT;

-- REQUEST references CATEGORY, PRIORITY, USER, ROOM, ASSET, STATUS
ALTER TABLE request
    ADD CONSTRAINT fk_request_category
    FOREIGN KEY (category_id) REFERENCES category (category_id)
    ON DELETE RESTRICT;

ALTER TABLE request
    ADD CONSTRAINT fk_request_priority
    FOREIGN KEY (priority_id) REFERENCES priority (priority_id)
    ON DELETE RESTRICT;

ALTER TABLE request
    ADD CONSTRAINT fk_request_requested_by
    FOREIGN KEY (requested_by) REFERENCES "user" (user_id)
    ON DELETE RESTRICT;

ALTER TABLE request
    ADD CONSTRAINT fk_request_room
    FOREIGN KEY (room_id) REFERENCES room (room_id)
    ON DELETE RESTRICT;

ALTER TABLE request
    ADD CONSTRAINT fk_request_asset
    FOREIGN KEY (asset_id) REFERENCES asset (asset_id)
    ON DELETE RESTRICT;

ALTER TABLE request
    ADD CONSTRAINT fk_request_status
    FOREIGN KEY (status_id) REFERENCES status (status_id)
    ON DELETE RESTRICT;

ALTER TABLE request
    ADD CONSTRAINT fk_request_closed_by
    FOREIGN KEY (closed_by) REFERENCES "user" (user_id)
    ON DELETE RESTRICT;

-- ASSIGNMENT references REQUEST, TECHNICIAN
ALTER TABLE assignment
    ADD CONSTRAINT fk_assignment_request
    FOREIGN KEY (request_id) REFERENCES request (request_id)
    ON DELETE CASCADE;

ALTER TABLE assignment
    ADD CONSTRAINT fk_assignment_technician
    FOREIGN KEY (technician_id) REFERENCES technician (technician_id)
    ON DELETE RESTRICT;

-- WORK_LOG references ASSIGNMENT
ALTER TABLE work_log
    ADD CONSTRAINT fk_work_log_assignment
    FOREIGN KEY (assignment_id) REFERENCES assignment (assignment_id)
    ON DELETE CASCADE;

-- WORK_LOG_MATERIAL references WORK_LOG, MATERIAL, TECHNICIAN
ALTER TABLE work_log_material
    ADD CONSTRAINT fk_wlm_work_log
    FOREIGN KEY (work_log_id) REFERENCES work_log (work_log_id)
    ON DELETE CASCADE;

ALTER TABLE work_log_material
    ADD CONSTRAINT fk_wlm_material
    FOREIGN KEY (material_id) REFERENCES material (material_id)
    ON DELETE RESTRICT;

ALTER TABLE work_log_material
    ADD CONSTRAINT fk_wlm_issued_by
    FOREIGN KEY (issued_by) REFERENCES technician (technician_id)
    ON DELETE RESTRICT;

-- STATUS_HISTORY references REQUEST, STATUS, USER
ALTER TABLE status_history
    ADD CONSTRAINT fk_sh_request
    FOREIGN KEY (request_id) REFERENCES request (request_id)
    ON DELETE CASCADE;

ALTER TABLE status_history
    ADD CONSTRAINT fk_sh_status
    FOREIGN KEY (status_id) REFERENCES status (status_id)
    ON DELETE RESTRICT;

ALTER TABLE status_history
    ADD CONSTRAINT fk_sh_changed_by
    FOREIGN KEY (changed_by) REFERENCES "user" (user_id)
    ON DELETE RESTRICT;

-- COST references REQUEST
ALTER TABLE cost
    ADD CONSTRAINT fk_cost_request
    FOREIGN KEY (request_id) REFERENCES request (request_id)
    ON DELETE CASCADE;

-- FEEDBACK references REQUEST, USER
ALTER TABLE feedback
    ADD CONSTRAINT fk_feedback_request
    FOREIGN KEY (request_id) REFERENCES request (request_id)
    ON DELETE CASCADE;

ALTER TABLE feedback
    ADD CONSTRAINT fk_feedback_user
    FOREIGN KEY (user_id) REFERENCES "user" (user_id)
    ON DELETE RESTRICT;

-- ============================================================================
-- 2. UNIQUE CONSTRAINTS
-- ============================================================================

ALTER TABLE role
    ADD CONSTRAINT uq_role_name UNIQUE (role_name);

ALTER TABLE "user"
    ADD CONSTRAINT uq_user_email UNIQUE (email);

ALTER TABLE priority
    ADD CONSTRAINT uq_priority_level UNIQUE (priority_level);

ALTER TABLE status
    ADD CONSTRAINT uq_status_name UNIQUE (status_name);

ALTER TABLE request
    ADD CONSTRAINT uq_request_number UNIQUE (request_number);

-- Enforces at most one feedback record per maintenance request (1:0..1)
ALTER TABLE feedback
    ADD CONSTRAINT uq_feedback_request UNIQUE (request_id);

-- Enforces unique room numbers within a given building
ALTER TABLE room
    ADD CONSTRAINT uq_room_building_number UNIQUE (building_id, room_number);

-- ============================================================================
-- 3. CHECK CONSTRAINTS
-- ============================================================================

-- Room floor validation (0 = Ground Floor)
ALTER TABLE room
    ADD CONSTRAINT chk_room_floor
    CHECK (floor >= 0);

-- Priority response time and allowed levels
ALTER TABLE priority
    ADD CONSTRAINT chk_priority_response_time
    CHECK (response_time_hr >= 0);

ALTER TABLE priority
    ADD CONSTRAINT chk_priority_level
    CHECK (priority_level IN ('Low', 'Medium', 'High', 'Critical'));

-- Technician hourly rate
ALTER TABLE technician
    ADD CONSTRAINT chk_technician_labor_rate
    CHECK (labor_rate >= 0);

-- Material unit cost and stock level
ALTER TABLE material
    ADD CONSTRAINT chk_material_unit_cost
    CHECK (unit_cost >= 0);

ALTER TABLE material
    ADD CONSTRAINT chk_material_stock_qty
    CHECK (stock_qty >= 0);

-- Work log labor hours spent
ALTER TABLE work_log
    ADD CONSTRAINT chk_work_log_hours_spent
    CHECK (hours_spent >= 0);

-- Material quantity used must be strictly positive
ALTER TABLE work_log_material
    ADD CONSTRAINT chk_wlm_quantity_used
    CHECK (quantity_used > 0);

-- Cost ledger amount and type validation
ALTER TABLE cost
    ADD CONSTRAINT chk_cost_amount
    CHECK (amount >= 0);

ALTER TABLE cost
    ADD CONSTRAINT chk_cost_type
    CHECK (cost_type IN ('Material', 'Labor', 'Service', 'Miscellaneous'));

-- Feedback satisfaction score (1 to 5)
ALTER TABLE feedback
    ADD CONSTRAINT chk_feedback_rating
    CHECK (rating >= 1 AND rating <= 5);

-- Assignment completion due date cannot precede assignment date
ALTER TABLE assignment
    ADD CONSTRAINT chk_assignment_due_date
    CHECK (due_date IS NULL OR due_date >= assigned_date);

-- Request closed date cannot precede submission date
ALTER TABLE request
    ADD CONSTRAINT chk_request_closed_date
    CHECK (closed_date IS NULL OR closed_date >= request_date);

-- Closure fields atomicity: all must be present if closed, all null if not closed
ALTER TABLE request
    ADD CONSTRAINT chk_request_closure_fields_atomic
    CHECK (
        (closed_date IS NULL AND resolution_description IS NULL AND closed_by IS NULL)
        OR
        (closed_date IS NOT NULL AND resolution_description IS NOT NULL AND closed_by IS NOT NULL)
    );

-- ============================================================================
-- 4. CROSS-TABLE INTEGRITY FUNCTIONS & TRIGGERS
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Trigger 1: Enforce Request Closure Integrity
-- Ensures that when a request is marked 'Closed', all closure attributes
-- are populated and consistent with the status lookup.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_check_request_closure_status()
RETURNS TRIGGER AS $$
DECLARE
    v_status_name VARCHAR(50);
BEGIN
    SELECT status_name INTO v_status_name
    FROM status
    WHERE status_id = NEW.status_id;

    IF v_status_name = 'Closed' THEN
        IF NEW.closed_date IS NULL OR NEW.resolution_description IS NULL OR NEW.closed_by IS NULL THEN
            RAISE EXCEPTION 'Request cannot be marked Closed without closed_date, resolution_description, and closed_by';
        END IF;
    ELSE
        -- If status is NOT 'Closed', closure fields should not be populated
        IF NEW.closed_date IS NOT NULL OR NEW.resolution_description IS NOT NULL OR NEW.closed_by IS NOT NULL THEN
            RAISE EXCEPTION 'Non-closed request cannot have closure details populated';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_check_request_closure
    BEFORE INSERT OR UPDATE OF status_id, closed_date, resolution_description, closed_by
    ON request
    FOR EACH ROW
    EXECUTE FUNCTION fn_check_request_closure_status();

-- ----------------------------------------------------------------------------
-- Trigger 2: Enforce Feedback Submission Eligibility
-- Ensures feedback is only accepted for requests that are currently 'Closed'
-- and feedback date does not precede the request submission or closure.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_check_feedback_eligibility()
RETURNS TRIGGER AS $$
DECLARE
    v_status_name VARCHAR(50);
    v_req_date    TIMESTAMP;
    v_closed_date TIMESTAMP;
BEGIN
    SELECT s.status_name, r.request_date, r.closed_date
    INTO v_status_name, v_req_date, v_closed_date
    FROM request r
    JOIN status s ON r.status_id = s.status_id
    WHERE r.request_id = NEW.request_id;

    IF v_status_name IS NULL THEN
        RAISE EXCEPTION 'Referenced request ID % does not exist', NEW.request_id;
    END IF;

    IF v_status_name <> 'Closed' THEN
        RAISE EXCEPTION 'Feedback can only be submitted for Closed requests. Current status: %', v_status_name;
    END IF;

    IF NEW.feedback_date < v_req_date THEN
        RAISE EXCEPTION 'Feedback date (%) cannot precede request submission date (%)', NEW.feedback_date, v_req_date;
    END IF;

    IF v_closed_date IS NOT NULL AND NEW.feedback_date < v_closed_date THEN
        RAISE EXCEPTION 'Feedback date (%) cannot precede request closure date (%)', NEW.feedback_date, v_closed_date;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_check_feedback_eligibility
    BEFORE INSERT OR UPDATE OF request_id, feedback_date
    ON feedback
    FOR EACH ROW
    EXECUTE FUNCTION fn_check_feedback_eligibility();

-- ----------------------------------------------------------------------------
-- Trigger 3: Enforce Material Stock Availability
-- Protects inventory by rejecting any requisition that exceeds current stock.
-- (Note: Atomic deduction is performed by the transactional backend service).
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_check_material_stock()
RETURNS TRIGGER AS $$
DECLARE
    v_available_qty INTEGER;
    v_item_name     VARCHAR(100);
BEGIN
    SELECT stock_qty, material_name
    INTO v_available_qty, v_item_name
    FROM material
    WHERE material_id = NEW.material_id;

    IF v_available_qty IS NULL THEN
        RAISE EXCEPTION 'Material ID % does not exist', NEW.material_id;
    END IF;

    IF NEW.quantity_used > v_available_qty THEN
        RAISE EXCEPTION 'Insufficient stock for material "%" (ID: %). Available: %, Requested: %',
            v_item_name, NEW.material_id, v_available_qty, NEW.quantity_used;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_check_material_stock
    BEFORE INSERT ON work_log_material
    FOR EACH ROW
    EXECUTE FUNCTION fn_check_material_stock();
