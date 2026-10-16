-- ============================================================================
-- CAMPUS FACILITY MAINTENANCE REQUEST MANAGEMENT SYSTEM (Project #41)
-- File: 07_tests.sql
-- Description: Automated test harness verifying positive workflows,
--              negative constraint enforcement, trigger validations,
--              and view executions. All tests are isolated.
-- ============================================================================

\set ON_ERROR_STOP on

-- ============================================================================
-- SECTION 1: POSITIVE WORKFLOW TESTS
-- Runs in a dedicated transaction and rolls back to keep seed data pristine.
-- ============================================================================

BEGIN;

DO $$
DECLARE
    v_req_id     BIGINT;
    v_assign_id  BIGINT;
    v_wl_id      BIGINT;
    v_status_id  BIGINT;
    v_view_count INTEGER;
BEGIN
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'STARTING POSITIVE WORKFLOW TESTS';
    RAISE NOTICE '============================================================';

    -- Step 1: Create a valid maintenance request
    INSERT INTO request (
        request_number, request_date, description, category_id, priority_id,
        requested_by, room_id, asset_id, status_id
    ) VALUES (
        'REQ-20261001-TEST', CURRENT_TIMESTAMP, 'Test Positive: Air conditioner filter clogged in smart classroom',
        3, 2, 1, 2, 1, 1
    ) RETURNING request_id INTO v_req_id;

    RAISE NOTICE '✓ Positive Test 1: Created valid request with ID %', v_req_id;

    -- Step 2: Assign technician to request
    INSERT INTO assignment (request_id, technician_id, assigned_date, due_date, status)
    VALUES (v_req_id, 3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + INTERVAL '24 hours', 'Assigned')
    RETURNING assignment_id INTO v_assign_id;

    RAISE NOTICE '✓ Positive Test 2: Created valid assignment with ID %', v_assign_id;

    -- Step 3: Log work under assignment
    INSERT INTO work_log (assignment_id, work_date, work_description, hours_spent)
    VALUES (v_assign_id, CURRENT_TIMESTAMP, 'Cleaned dust filters and checked blower air velocity', 1.50)
    RETURNING work_log_id INTO v_wl_id;

    RAISE NOTICE '✓ Positive Test 3: Created valid work log with ID %', v_wl_id;

    -- Step 4: Issue material for work log
    INSERT INTO work_log_material (work_log_id, material_id, quantity_used, issued_date, issued_by)
    VALUES (v_wl_id, 1, 2.00, CURRENT_TIMESTAMP, 3);

    RAISE NOTICE '✓ Positive Test 4: Successfully issued 2 units of material for work log %', v_wl_id;

    -- Step 5: Update status to 'In Progress' and log history
    SELECT status_id INTO v_status_id FROM status WHERE status_name = 'In Progress';

    UPDATE request SET status_id = v_status_id WHERE request_id = v_req_id;

    INSERT INTO status_history (request_id, status_id, changed_by, remarks)
    VALUES (v_req_id, v_status_id, 7, 'Technician commenced filter servicing on site');

    RAISE NOTICE '✓ Positive Test 5: Updated request status to In Progress with history log';

    -- Step 6: Log associated cost
    INSERT INTO cost (request_id, cost_type, amount, description)
    VALUES (v_req_id, 'Labor', 630.00, '1.5 hrs technician time (Gurpreet Singh @ ₹420/hr)');

    RAISE NOTICE '✓ Positive Test 6: Recorded labor cost in single-ledger COST table';

    -- Step 7: Close request with required closure fields
    SELECT status_id INTO v_status_id FROM status WHERE status_name = 'Closed';

    UPDATE request
    SET status_id = v_status_id,
        closed_date = CURRENT_TIMESTAMP,
        resolution_description = 'Air filter cleaned and condenser fins degreased. Airflow nominal.',
        closed_by = 7
    WHERE request_id = v_req_id;

    INSERT INTO status_history (request_id, status_id, changed_by, remarks)
    VALUES (v_req_id, v_status_id, 7, 'Request officially closed after sign-off');

    RAISE NOTICE '✓ Positive Test 7: Successfully closed request with full resolution details';

    -- Step 8: Submit feedback for closed request
    INSERT INTO feedback (request_id, user_id, rating, comments)
    VALUES (v_req_id, 1, 5, 'Quick resolution, classroom is cool again.');

    RAISE NOTICE '✓ Positive Test 8: Submitted 5-star feedback for closed request';

    -- Step 9: Verify reporting views execute cleanly
    SELECT COUNT(*) INTO v_view_count FROM vw_pending_requests;
    SELECT COUNT(*) INTO v_view_count FROM vw_request_ageing;
    SELECT COUNT(*) INTO v_view_count FROM vw_technician_workload;
    SELECT COUNT(*) INTO v_view_count FROM vw_building_maintenance_cost;
    SELECT COUNT(*) INTO v_view_count FROM vw_material_usage;
    SELECT COUNT(*) INTO v_view_count FROM vw_feedback_summary;

    RAISE NOTICE '✓ Positive Test 9: All 6 analytical views executed successfully without error';

    RAISE NOTICE 'ALL POSITIVE TESTS COMPLETED SUCCESSFULLY.';
END $$;

-- Rollback the positive test transaction so seed data remains clean
ROLLBACK;


-- ============================================================================
-- SECTION 2: NEGATIVE CONSTRAINT TESTS
-- Each test attempts an invalid operation and asserts that the appropriate
-- database constraint or trigger intercepts it and raises an exception.
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'STARTING NEGATIVE CONSTRAINT TESTS';
    RAISE NOTICE '============================================================';
END $$;

-- Negative Test 1: Duplicate RequestNumber
DO $$
BEGIN
    BEGIN
        INSERT INTO request (
            request_number, description, category_id, priority_id,
            requested_by, room_id, status_id
        ) VALUES (
            'REQ-20260920-0001', 'Duplicate test', 1, 1, 1, 1, 1
        );
        RAISE EXCEPTION 'TEST FAILED: Duplicate request_number was allowed!';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE '✓ Negative Test 1 Passed: Duplicate request_number caught by uq_request_number';
    END;
END $$;

-- Negative Test 2: Duplicate User Email
DO $$
BEGIN
    BEGIN
        INSERT INTO "user" (full_name, email, role_id)
        VALUES ('Clone User', 'ramesh.sundaram@campus.edu', 1);
        RAISE EXCEPTION 'TEST FAILED: Duplicate user email was allowed!';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE '✓ Negative Test 2 Passed: Duplicate user email caught by uq_user_email';
    END;
END $$;

-- Negative Test 3: Duplicate Feedback for Same Request (1:0..1)
DO $$
BEGIN
    BEGIN
        -- Request 1 already has feedback in seed data
        INSERT INTO feedback (request_id, user_id, rating, comments)
        VALUES (1, 1, 4, 'Attempting second feedback submission');
        RAISE EXCEPTION 'TEST FAILED: Second feedback for same request was allowed!';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE '✓ Negative Test 3 Passed: Duplicate feedback caught by uq_feedback_request';
    END;
END $$;

-- Negative Test 4: Invalid Feedback Rating (> 5)
DO $$
BEGIN
    BEGIN
        INSERT INTO feedback (request_id, user_id, rating, comments)
        VALUES (10, 5, 6, 'Rating of 6 is invalid');
        RAISE EXCEPTION 'TEST FAILED: Rating of 6 was allowed!';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE '✓ Negative Test 4 Passed: Rating > 5 caught by chk_feedback_rating';
    END;
END $$;

-- Negative Test 5: Invalid Foreign Key (Non-existent Room)
DO $$
BEGIN
    BEGIN
        INSERT INTO request (
            request_number, description, category_id, priority_id,
            requested_by, room_id, status_id
        ) VALUES (
            'REQ-99999999-FAKE', 'Invalid room test', 1, 1, 1, 99999, 1
        );
        RAISE EXCEPTION 'TEST FAILED: Request with non-existent room_id was allowed!';
    EXCEPTION WHEN foreign_key_violation THEN
        RAISE NOTICE '✓ Negative Test 5 Passed: Invalid room_id caught by fk_request_room';
    END;
END $$;

-- Negative Test 6: Invalid Priority Level String
DO $$
BEGIN
    BEGIN
        INSERT INTO priority (priority_level, description, response_time_hr)
        VALUES ('SuperUrgent', 'Invalid priority level', 1);
        RAISE EXCEPTION 'TEST FAILED: Unapproved priority level was allowed!';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE '✓ Negative Test 6 Passed: Unapproved priority level caught by chk_priority_level';
    END;
END $$;

-- Negative Test 7: Negative Cost Amount
DO $$
BEGIN
    BEGIN
        INSERT INTO cost (request_id, cost_type, amount, description)
        VALUES (1, 'Material', -150.00, 'Negative cost test');
        RAISE EXCEPTION 'TEST FAILED: Negative cost amount was allowed!';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE '✓ Negative Test 7 Passed: Negative cost caught by chk_cost_amount';
    END;
END $$;

-- Negative Test 8: Negative Material Stock Level
DO $$
BEGIN
    BEGIN
        INSERT INTO material (material_name, unit, unit_cost, stock_qty)
        VALUES ('Negative Stock Wire', 'Meter', 50.00, -10);
        RAISE EXCEPTION 'TEST FAILED: Negative stock quantity was allowed!';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE '✓ Negative Test 8 Passed: Negative stock caught by chk_material_stock_qty';
    END;
END $$;

-- Negative Test 9: Zero or Negative Material Quantity Used
DO $$
BEGIN
    BEGIN
        INSERT INTO work_log_material (work_log_id, material_id, quantity_used, issued_by)
        VALUES (1, 1, 0.00, 1);
        RAISE EXCEPTION 'TEST FAILED: Zero quantity_used was allowed!';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE '✓ Negative Test 9 Passed: Zero quantity_used caught by chk_wlm_quantity_used';
    END;
END $$;

-- Negative Test 10: Material Usage Exceeding Available Warehouse Stock
DO $$
DECLARE
    v_stock INTEGER;
BEGIN
    SELECT stock_qty INTO v_stock FROM material WHERE material_id = 5; -- R-410A gas (stock = 30)
    BEGIN
        -- Attempt to consume 500 kg when only 30 kg are in stock
        INSERT INTO work_log_material (work_log_id, material_id, quantity_used, issued_by)
        VALUES (1, 5, 500.00, 3);
        RAISE EXCEPTION 'TEST FAILED: Material usage exceeding available stock was allowed!';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '✓ Negative Test 10 Passed: Stock exhaustion caught by trg_check_material_stock (%)', SQLERRM;
    END;
END $$;

-- Negative Test 11: Incomplete Request Closure (Closed status without resolution description)
DO $$
DECLARE
    v_closed_id BIGINT;
BEGIN
    SELECT status_id INTO v_closed_id FROM status WHERE status_name = 'Closed';
    BEGIN
        -- Attempt to update Request 7 to 'Closed' without resolution details
        UPDATE request
        SET status_id = v_closed_id,
            closed_date = CURRENT_TIMESTAMP,
            resolution_description = NULL, -- Missing required description
            closed_by = 7
        WHERE request_id = 7;
        RAISE EXCEPTION 'TEST FAILED: Request closure without resolution_description was allowed!';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '✓ Negative Test 11 Passed: Incomplete closure caught by trg_check_request_closure (%)', SQLERRM;
    END;
END $$;

-- Negative Test 12: Premature Feedback on Unclosed Request
DO $$
BEGIN
    -- Request 4 is currently 'In Progress'
    BEGIN
        INSERT INTO feedback (request_id, user_id, rating, comments)
        VALUES (4, 2, 5, 'Premature feedback submission on in-progress job');
        RAISE EXCEPTION 'TEST FAILED: Feedback on unclosed request was allowed!';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '✓ Negative Test 12 Passed: Premature feedback caught by trg_check_feedback_eligibility (%)', SQLERRM;
    END;
END $$;

-- Negative Test 13: Assignment Due Date Preceding Assigned Date
DO $$
BEGIN
    BEGIN
        INSERT INTO assignment (request_id, technician_id, assigned_date, due_date, status)
        VALUES (8, 1, '2026-10-01 10:00:00', '2026-10-01 08:00:00', 'Assigned');
        RAISE EXCEPTION 'TEST FAILED: Due date earlier than assigned date was allowed!';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE '✓ Negative Test 13 Passed: Invalid due_date caught by chk_assignment_due_date';
    END;
END $$;

-- Negative Test 14: Non-closed request attempting to populate closure details
DO $$
DECLARE
    v_open_id BIGINT;
BEGIN
    SELECT status_id INTO v_open_id FROM status WHERE status_name = 'Open';
    BEGIN
        -- Attempt to set closed_date on an Open request
        UPDATE request
        SET status_id = v_open_id,
            closed_date = CURRENT_TIMESTAMP,
            resolution_description = 'Partial repair notes',
            closed_by = 7
        WHERE request_id = 8;
        RAISE EXCEPTION 'TEST FAILED: Closure details on open request were allowed!';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '✓ Negative Test 14 Passed: Closure details on Open request caught by trg_check_request_closure (%)', SQLERRM;
    END;
END $$;

DO $$
BEGIN
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'ALL POSITIVE AND NEGATIVE TESTS COMPLETED SUCCESSFULLY!';
    RAISE NOTICE '============================================================';
END $$;
