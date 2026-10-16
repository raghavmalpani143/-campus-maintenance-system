-- ============================================================================
-- CAMPUS FACILITY MAINTENANCE REQUEST MANAGEMENT SYSTEM (Project #41)
-- File: 03_indexes.sql
-- Description: Targeted indexes for foreign key joins, operational filtering,
--              and analytical reporting performance.
-- ============================================================================

-- ============================================================================
-- 1. FOREIGN KEY JOIN INDEXES
-- Accelerates cascading referential checks, relational joins, and navigations.
-- ============================================================================

-- ROOM foreign keys
CREATE INDEX idx_room_building_id ON room (building_id);

-- ASSET foreign keys
CREATE INDEX idx_asset_room_id ON asset (room_id);

-- USER foreign keys
CREATE INDEX idx_user_role_id ON "user" (role_id);

-- REQUEST foreign keys
CREATE INDEX idx_request_category_id ON request (category_id);
CREATE INDEX idx_request_priority_id ON request (priority_id);
CREATE INDEX idx_request_requested_by ON request (requested_by);
CREATE INDEX idx_request_room_id ON request (room_id);
CREATE INDEX idx_request_asset_id ON request (asset_id);
CREATE INDEX idx_request_status_id ON request (status_id);
CREATE INDEX idx_request_closed_by ON request (closed_by);

-- ASSIGNMENT foreign keys
CREATE INDEX idx_assignment_request_id ON assignment (request_id);
CREATE INDEX idx_assignment_technician_id ON assignment (technician_id);

-- WORK_LOG foreign keys
CREATE INDEX idx_work_log_assignment_id ON work_log (assignment_id);

-- WORK_LOG_MATERIAL foreign keys
-- Note: work_log_id is the leading column of the composite PK, so only material_id and issued_by need separate indexes.
CREATE INDEX idx_wlm_material_id ON work_log_material (material_id);
CREATE INDEX idx_wlm_issued_by ON work_log_material (issued_by);

-- STATUS_HISTORY foreign keys
CREATE INDEX idx_status_history_request_id ON status_history (request_id);
CREATE INDEX idx_status_history_status_id ON status_history (status_id);
CREATE INDEX idx_status_history_changed_by ON status_history (changed_by);

-- COST foreign keys
CREATE INDEX idx_cost_request_id ON cost (request_id);

-- FEEDBACK foreign keys
-- Note: request_id is already indexed by uq_feedback_request UNIQUE constraint.
CREATE INDEX idx_feedback_user_id ON feedback (user_id);

-- ============================================================================
-- 2. OPERATIONAL FILTERING & REPORTING INDEXES
-- Optimizes high-frequency queries, dashboard views, and analytical aggregations.
-- ============================================================================

-- Ageing reports and chronological request sorting
CREATE INDEX idx_request_request_date ON request (request_date);

-- Technician workload and active assignment filtering
CREATE INDEX idx_assignment_status ON assignment (status);

-- Status history chronological sorting for audit trail inspection
CREATE INDEX idx_status_history_changed_date ON status_history (changed_date);

-- Cost type breakdown reports (e.g. Material vs Labor vs Service)
CREATE INDEX idx_cost_cost_type ON cost (cost_type);

-- Asset type and operational status filtering
CREATE INDEX idx_asset_status ON asset (status);
