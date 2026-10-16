-- ============================================================================
-- CAMPUS FACILITY MAINTENANCE REQUEST MANAGEMENT SYSTEM (Project #41)
-- File: 06_views.sql
-- Description: Core analytical and operational reporting views.
-- Standards: Follows the approved single-ledger COST accounting model.
-- ============================================================================

-- ============================================================================
-- 1. VIEW: vw_pending_requests
-- Purpose: Real-time operational dashboard of all active, unclosed requests
--          with location, SLA, and technician assignment status.
-- ============================================================================
CREATE OR REPLACE VIEW vw_pending_requests AS
SELECT
    r.request_id,
    r.request_number,
    r.request_date,
    c.category_name,
    p.priority_level,
    p.response_time_hr AS sla_target_hours,
    b.building_name,
    rm.room_number,
    u.full_name        AS requester_name,
    s.status_name      AS current_status,
    ROUND(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - r.request_date)) / 86400.0, 1) AS days_open,
    COALESCE(t.full_name, 'UNASSIGNED') AS assigned_technician,
    a.status           AS assignment_status
FROM request r
JOIN category c  ON r.category_id = c.category_id
JOIN priority p  ON r.priority_id = p.priority_id
JOIN status s    ON r.status_id = s.status_id
JOIN "user" u    ON r.requested_by = u.user_id
JOIN room rm     ON r.room_id = rm.room_id
JOIN building b  ON rm.building_id = b.building_id
LEFT JOIN assignment a ON r.request_id = a.request_id AND a.status IN ('Assigned', 'In Progress')
LEFT JOIN technician t ON a.technician_id = t.technician_id
WHERE s.status_name <> 'Closed';

-- ============================================================================
-- 2. VIEW: vw_request_ageing
-- Purpose: Tracks elapsed resolution hours against SLA benchmarks,
--          categorizing requests into ageing brackets and SLA compliance states.
-- ============================================================================
CREATE OR REPLACE VIEW vw_request_ageing AS
SELECT
    r.request_id,
    r.request_number,
    r.request_date,
    r.closed_date,
    s.status_name AS request_status,
    p.priority_level,
    p.response_time_hr AS sla_target_hours,
    ROUND(EXTRACT(EPOCH FROM (COALESCE(r.closed_date, CURRENT_TIMESTAMP) - r.request_date)) / 3600.0, 2) AS hours_open,
    CASE
        WHEN s.status_name = 'Closed' AND EXTRACT(EPOCH FROM (r.closed_date - r.request_date)) / 3600.0 <= p.response_time_hr
            THEN 'MET SLA'
        WHEN s.status_name = 'Closed' AND EXTRACT(EPOCH FROM (r.closed_date - r.request_date)) / 3600.0 > p.response_time_hr
            THEN 'BREACHED SLA'
        WHEN s.status_name <> 'Closed' AND EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - r.request_date)) / 3600.0 > p.response_time_hr
            THEN 'OVERDUE (In Progress)'
        ELSE 'WITHIN SLA (In Progress)'
    END AS sla_performance_status,
    CASE
        WHEN EXTRACT(EPOCH FROM (COALESCE(r.closed_date, CURRENT_TIMESTAMP) - r.request_date)) / 3600.0 < 24.0
            THEN '< 24 Hours'
        WHEN EXTRACT(EPOCH FROM (COALESCE(r.closed_date, CURRENT_TIMESTAMP) - r.request_date)) / 3600.0 <= 72.0
            THEN '24 - 72 Hours'
        ELSE '> 72 Hours'
    END AS ageing_bracket,
    b.building_name,
    rm.room_number
FROM request r
JOIN priority p  ON r.priority_id = p.priority_id
JOIN status s    ON r.status_id = s.status_id
JOIN room rm     ON r.room_id = rm.room_id
JOIN building b  ON rm.building_id = b.building_id;

-- ============================================================================
-- 3. VIEW: vw_technician_workload
-- Purpose: Resource management view summarizing technician job volume,
--          active assignments, completed jobs, and accumulated labor hours.
-- ============================================================================
CREATE OR REPLACE VIEW vw_technician_workload AS
SELECT
    t.technician_id,
    t.full_name,
    t.department,
    t.status AS technician_status,
    t.labor_rate,
    COUNT(a.assignment_id)                                  AS total_assignments,
    COUNT(CASE WHEN a.status IN ('Assigned', 'In Progress') THEN 1 END) AS active_assignments,
    COUNT(CASE WHEN a.status = 'Completed' THEN 1 END)      AS completed_assignments,
    COALESCE(SUM(wl.hours_spent), 0.00)                     AS total_hours_worked,
    ROUND(COALESCE(SUM(wl.hours_spent * t.labor_rate), 0.00), 2) AS total_labor_value_generated
FROM technician t
LEFT JOIN assignment a ON t.technician_id = a.technician_id
LEFT JOIN work_log wl  ON a.assignment_id = wl.assignment_id
GROUP BY t.technician_id, t.full_name, t.department, t.status, t.labor_rate;

-- ============================================================================
-- 4. VIEW: vw_building_maintenance_cost
-- Purpose: Financial reporting aggregating maintenance expenses by campus building.
-- Accounting Rule: Aggregates directly from the COST table (single recorded-cost
--                  ledger) to guarantee no double-counting occurs.
-- ============================================================================
CREATE OR REPLACE VIEW vw_building_maintenance_cost AS
SELECT
    b.building_id,
    b.building_name,
    b.location,
    COUNT(DISTINCT r.request_id)                            AS total_requests_count,
    COALESCE(SUM(c.amount), 0.00)                           AS total_maintenance_expenditure,
    COALESCE(SUM(CASE WHEN c.cost_type = 'Material' THEN c.amount ELSE 0 END), 0.00) AS material_cost,
    COALESCE(SUM(CASE WHEN c.cost_type = 'Labor' THEN c.amount ELSE 0 END), 0.00)    AS labor_cost,
    COALESCE(SUM(CASE WHEN c.cost_type = 'Service' THEN c.amount ELSE 0 END), 0.00)  AS service_cost,
    COALESCE(SUM(CASE WHEN c.cost_type = 'Miscellaneous' THEN c.amount ELSE 0 END), 0.00) AS misc_cost
FROM building b
LEFT JOIN room rm   ON b.building_id = rm.building_id
LEFT JOIN request r ON rm.room_id = r.room_id
LEFT JOIN cost c    ON r.request_id = c.request_id
GROUP BY b.building_id, b.building_name, b.location;

-- ============================================================================
-- 5. VIEW: vw_material_usage
-- Purpose: Inventory consumption analytics tracking quantities and costs issued
--          against remaining warehouse stock levels.
-- ============================================================================
CREATE OR REPLACE VIEW vw_material_usage AS
SELECT
    m.material_id,
    m.material_name,
    m.unit,
    m.unit_cost,
    m.stock_qty AS current_warehouse_stock,
    COALESCE(SUM(wlm.quantity_used), 0.00)                          AS total_quantity_used,
    ROUND(COALESCE(SUM(wlm.quantity_used * m.unit_cost), 0.00), 2)  AS total_material_cost,
    COUNT(DISTINCT wlm.work_log_id)                                 AS total_work_orders_used_in
FROM material m
LEFT JOIN work_log_material wlm ON m.material_id = wlm.material_id
GROUP BY m.material_id, m.material_name, m.unit, m.unit_cost, m.stock_qty;

-- ============================================================================
-- 6. VIEW: vw_feedback_summary
-- Purpose: Quality assurance view analyzing requester satisfaction ratings
--          and feedback volume by building and category.
-- ============================================================================
CREATE OR REPLACE VIEW vw_feedback_summary AS
SELECT
    b.building_name,
    c.category_name,
    COUNT(f.feedback_id)    AS total_evaluations,
    ROUND(AVG(f.rating), 2) AS average_rating,
    MIN(f.rating)           AS lowest_rating,
    MAX(f.rating)           AS highest_rating
FROM feedback f
JOIN request r   ON f.request_id = r.request_id
JOIN room rm     ON r.room_id = rm.room_id
JOIN building b  ON rm.building_id = b.building_id
JOIN category c  ON r.category_id = c.category_id
GROUP BY b.building_id, b.building_name, c.category_id, c.category_name;
