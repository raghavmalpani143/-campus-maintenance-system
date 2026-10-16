-- ============================================================================
-- CAMPUS FACILITY MAINTENANCE REQUEST MANAGEMENT SYSTEM (Project #41)
-- File: 05_queries.sql
-- Description: Comprehensive query suite demonstrating SQL concepts,
--              operational reporting, multi-table joins, aggregations,
--              subqueries, date/time math, and transaction patterns.
-- ============================================================================

-- ============================================================================
-- 1. BASIC SELECT, FILTERING, SORTING & STRING MATCHING
-- ============================================================================

-- Query 1.1: List all active inventory items with low stock (<= 50 units), ordered by unit cost descending
SELECT
    material_id,
    material_name,
    unit,
    unit_cost,
    stock_qty,
    status
FROM material
WHERE stock_qty <= 50 AND status = 'Active'
ORDER BY unit_cost DESC;

-- Query 1.2: Find requests mentioning 'leak', 'water', or 'flooding' in description
SELECT
    request_number,
    request_date,
    description
FROM request
WHERE description ILIKE '%leak%'
   OR description ILIKE '%water%'
   OR description ILIKE '%flood%'
ORDER BY request_date DESC;

-- ============================================================================
-- 2. INNER JOINS & MULTI-TABLE JOINS
-- ============================================================================

-- Query 2.1: Full operational detail of all requests with requester, room, building, category, and status
SELECT
    r.request_number,
    r.request_date,
    c.category_name,
    p.priority_level,
    p.response_time_hr AS sla_hours,
    s.status_name      AS current_status,
    u.full_name        AS requested_by_user,
    rm.room_number,
    b.building_name
FROM request r
JOIN category c  ON r.category_id = c.category_id
JOIN priority p  ON r.priority_id = p.priority_id
JOIN status s    ON r.status_id = s.status_id
JOIN "user" u    ON r.requested_by = u.user_id
JOIN room rm     ON r.room_id = rm.room_id
JOIN building b  ON rm.building_id = b.building_id
ORDER BY r.request_date DESC;

-- Query 2.2: Multi-table join showing work logs with technician, assignment, request, and room details
SELECT
    wl.work_log_id,
    wl.work_date,
    r.request_number,
    t.full_name         AS technician_name,
    t.department,
    wl.hours_spent,
    wl.work_description,
    rm.room_number,
    b.building_name
FROM work_log wl
JOIN assignment a  ON wl.assignment_id = a.assignment_id
JOIN request r     ON a.request_id = r.request_id
JOIN technician t  ON a.technician_id = t.technician_id
JOIN room rm       ON r.room_id = rm.room_id
JOIN building b    ON rm.building_id = b.building_id
ORDER BY wl.work_date DESC;

-- ============================================================================
-- 3. LEFT JOINS (Optional relationships & NULL handling)
-- ============================================================================

-- Query 3.1: All requests with optional asset details and optional closure/feedback info
SELECT
    r.request_number,
    r.description,
    COALESCE(ast.asset_name, 'General Room Defect (No Asset)') AS asset_name,
    COALESCE(ast.brand_model, 'N/A')                           AS asset_model,
    s.status_name                                              AS status,
    COALESCE(TO_CHAR(r.closed_date, 'YYYY-MM-DD HH24:MI'), 'Still Open') AS closed_time,
    f.rating,
    COALESCE(f.comments, 'No Feedback Submitted')              AS feedback_comment
FROM request r
JOIN status s        ON r.status_id = s.status_id
LEFT JOIN asset ast  ON r.asset_id = ast.asset_id
LEFT JOIN feedback f ON r.request_id = f.request_id
ORDER BY r.request_id;

-- Query 3.2: List all technicians and their assignments, including technicians with zero assignments
SELECT
    t.technician_id,
    t.full_name,
    t.department,
    COUNT(a.assignment_id)                                  AS total_assignments,
    COUNT(CASE WHEN a.status = 'In Progress' THEN 1 END)    AS active_assignments
FROM technician t
LEFT JOIN assignment a ON t.technician_id = a.technician_id
GROUP BY t.technician_id, t.full_name, t.department
ORDER BY total_assignments DESC, t.full_name;

-- ============================================================================
-- 4. AGGREGATIONS, GROUP BY & HAVING
-- ============================================================================

-- Query 4.1: Category breakdown: Total requests, closed count, and average response SLA
SELECT
    c.category_name,
    COUNT(r.request_id)                               AS total_requests,
    COUNT(CASE WHEN s.status_name = 'Closed' THEN 1 END) AS closed_requests,
    ROUND(AVG(p.response_time_hr), 1)                 AS avg_sla_hours
FROM category c
LEFT JOIN request r ON c.category_id = r.category_id
LEFT JOIN priority p ON r.priority_id = p.priority_id
LEFT JOIN status s   ON r.status_id = s.status_id
GROUP BY c.category_id, c.category_name
ORDER BY total_requests DESC;

-- Query 4.2: Technicians who have logged more than 3 total hours across all assignments (HAVING demonstration)
SELECT
    t.full_name,
    t.department,
    t.labor_rate,
    SUM(wl.hours_spent)                               AS total_hours_worked,
    ROUND(SUM(wl.hours_spent * t.labor_rate), 2)      AS total_labor_value
FROM technician t
JOIN assignment a ON t.technician_id = a.technician_id
JOIN work_log wl  ON a.assignment_id = wl.assignment_id
GROUP BY t.technician_id, t.full_name, t.department, t.labor_rate
HAVING SUM(wl.hours_spent) >= 3.00
ORDER BY total_hours_worked DESC;

-- ============================================================================
-- 5. SUBQUERIES & NESTED QUERIES (EXISTS, NOT EXISTS, Scalar Subqueries)
-- ============================================================================

-- Query 5.1: Requests whose total incurred cost is greater than the campus average request cost
SELECT
    r.request_number,
    c_sub.total_request_cost,
    ROUND((SELECT AVG(total_cost) FROM (
        SELECT SUM(amount) AS total_cost FROM cost GROUP BY request_id
    ) avg_costs), 2) AS campus_avg_request_cost
FROM request r
JOIN (
    SELECT request_id, SUM(amount) AS total_request_cost
    FROM cost
    GROUP BY request_id
) c_sub ON r.request_id = c_sub.request_id
WHERE c_sub.total_request_cost > (
    SELECT AVG(total_cost) FROM (
        SELECT SUM(amount) AS total_cost FROM cost GROUP BY request_id
    ) avg_costs
)
ORDER BY c_sub.total_request_cost DESC;

-- Query 5.2: Materials that have NEVER been issued in any work log (NOT EXISTS)
SELECT
    m.material_id,
    m.material_name,
    m.unit,
    m.stock_qty,
    m.unit_cost
FROM material m
WHERE NOT EXISTS (
    SELECT 1
    FROM work_log_material wlm
    WHERE wlm.material_id = m.material_id
);

-- Query 5.3: Users who have submitted requests that required emergency HVAC repairs (EXISTS)
SELECT
    u.user_id,
    u.full_name,
    u.email
FROM "user" u
WHERE EXISTS (
    SELECT 1
    FROM request r
    JOIN category cat ON r.category_id = cat.category_id
    JOIN priority pri ON r.priority_id = pri.priority_id
    WHERE r.requested_by = u.user_id
      AND cat.category_name = 'HVAC'
      AND pri.priority_level = 'Critical'
);

-- ============================================================================
-- 6. CASE EXPRESSIONS & ADVANCED DATE/TIME CALCULATIONS
-- ============================================================================

-- Query 6.1: SLA Compliance & Turnaround Evaluation for Closed Requests
-- Compares actual hours taken to resolve against the priority SLA target.
SELECT
    r.request_number,
    p.priority_level,
    p.response_time_hr AS sla_target_hours,
    ROUND(EXTRACT(EPOCH FROM (r.closed_date - r.request_date)) / 3600.0, 2) AS actual_hours_taken,
    CASE
        WHEN EXTRACT(EPOCH FROM (r.closed_date - r.request_date)) / 3600.0 <= p.response_time_hr
            THEN 'MET SLA'
        ELSE 'BREACHED SLA'
    END AS sla_performance_status,
    r.resolution_description
FROM request r
JOIN priority p ON r.priority_id = p.priority_id
JOIN status s   ON r.status_id = s.status_id
WHERE s.status_name = 'Closed'
ORDER BY actual_hours_taken DESC;

-- Query 6.2: Request Ageing Bracket Breakdown for Active / Open Requests
SELECT
    r.request_number,
    b.building_name,
    rm.room_number,
    p.priority_level,
    s.status_name,
    ROUND(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - r.request_date)) / 3600.0, 1) AS hours_since_submission,
    CASE
        WHEN EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - r.request_date)) / 3600.0 < 24.0 THEN '0-24 Hours (Fresh)'
        WHEN EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - r.request_date)) / 3600.0 < 72.0 THEN '24-72 Hours (Aging)'
        ELSE '72+ Hours (Critical Overdue)'
    END AS ageing_bracket
FROM request r
JOIN room rm     ON r.room_id = rm.room_id
JOIN building b  ON rm.building_id = b.building_id
JOIN priority p  ON r.priority_id = p.priority_id
JOIN status s    ON r.status_id = s.status_id
WHERE s.status_name <> 'Closed'
ORDER BY r.request_date ASC;

-- ============================================================================
-- 7. CORE OPERATIONAL REPORTS
-- ============================================================================

-- Report 7.1: Pending Requests Report
SELECT
    r.request_number,
    r.request_date,
    cat.category_name,
    pri.priority_level,
    b.building_name,
    rm.room_number,
    st.status_name AS current_state,
    COALESCE(tech.full_name, 'UNASSIGNED') AS assigned_technician
FROM request r
JOIN category cat ON r.category_id = cat.category_id
JOIN priority pri ON r.priority_id = pri.priority_id
JOIN status st    ON r.status_id = st.status_id
JOIN room rm      ON r.room_id = rm.room_id
JOIN building b   ON rm.building_id = b.building_id
LEFT JOIN assignment a ON r.request_id = a.request_id AND a.status IN ('Assigned', 'In Progress')
LEFT JOIN technician tech ON a.technician_id = tech.technician_id
WHERE st.status_name <> 'Closed'
ORDER BY pri.response_time_hr ASC, r.request_date ASC;

-- Report 7.2: Building Maintenance Expenditure Report (Single-Ledger COST Aggregation)
-- Aggregates recorded COST entries grouped by building and cost type
SELECT
    b.building_id,
    b.building_name,
    b.location,
    COUNT(DISTINCT r.request_id)                   AS total_maintenance_requests,
    SUM(c.amount)                                  AS total_expenditure,
    SUM(CASE WHEN c.cost_type = 'Material' THEN c.amount ELSE 0 END) AS material_expenses,
    SUM(CASE WHEN c.cost_type = 'Labor' THEN c.amount ELSE 0 END)    AS labor_expenses,
    SUM(CASE WHEN c.cost_type = 'Service' THEN c.amount ELSE 0 END)  AS service_expenses,
    SUM(CASE WHEN c.cost_type = 'Miscellaneous' THEN c.amount ELSE 0 END) AS misc_expenses
FROM building b
JOIN room rm     ON b.building_id = rm.building_id
JOIN request r   ON rm.room_id = r.room_id
JOIN cost c      ON r.request_id = c.request_id
GROUP BY b.building_id, b.building_name, b.location
ORDER BY total_expenditure DESC;

-- Report 7.3: Material Consumption & Inventory Depletion
SELECT
    m.material_name,
    m.unit,
    m.unit_cost,
    SUM(wlm.quantity_used)                         AS total_quantity_consumed,
    ROUND(SUM(wlm.quantity_used * m.unit_cost), 2) AS total_material_cost,
    m.stock_qty                                    AS current_warehouse_stock,
    COUNT(DISTINCT wlm.work_log_id)                AS work_orders_count
FROM material m
JOIN work_log_material wlm ON m.material_id = wlm.material_id
GROUP BY m.material_id, m.material_name, m.unit, m.unit_cost, m.stock_qty
ORDER BY total_material_cost DESC;

-- Report 7.4: Requester Satisfaction & Feedback Summary
SELECT
    b.building_name,
    COUNT(f.feedback_id)                           AS total_surveys,
    ROUND(AVG(f.rating), 2)                        AS avg_satisfaction_rating,
    MIN(f.rating)                                  AS min_rating,
    MAX(f.rating)                                  AS max_rating
FROM feedback f
JOIN request r   ON f.request_id = r.request_id
JOIN room rm     ON r.room_id = rm.room_id
JOIN building b  ON rm.building_id = b.building_id
GROUP BY b.building_id, b.building_name
ORDER BY avg_satisfaction_rating DESC;

-- ============================================================================
-- 8. ATOMIC TRANSACTION WORKFLOW DEMONSTRATION
-- ============================================================================

-- Pattern 8.1: Status Update with Synchronized Audit History (BEGIN ... COMMIT)
-- Demonstrates atomic state progression from 'Assigned' to 'In Progress'
/*
BEGIN;

UPDATE request
SET status_id = (SELECT status_id FROM status WHERE status_name = 'In Progress')
WHERE request_id = 7;

INSERT INTO status_history (request_id, status_id, changed_by, changed_date, remarks)
VALUES (
    7,
    (SELECT status_id FROM status WHERE status_name = 'In Progress'),
    7,
    CURRENT_TIMESTAMP,
    'Technician arrived on site with hinge replacement toolkit'
);

COMMIT;
*/
