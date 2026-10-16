-- ============================================================================
-- CAMPUS FACILITY MAINTENANCE REQUEST MANAGEMENT SYSTEM (Project #41)
-- File: 04_seed_data.sql
-- Description: Deterministic, realistic campus seed data demonstrating
--              full maintenance workflows, reporting, and constraint compliance.
-- ============================================================================

-- Clean up any existing data in reverse-dependency order with reset identity sequences
TRUNCATE TABLE
    feedback,
    cost,
    status_history,
    work_log_material,
    work_log,
    assignment,
    request,
    material,
    technician,
    status,
    priority,
    category,
    "user",
    role,
    asset,
    room,
    building
RESTART IDENTITY CASCADE;

-- ============================================================================
-- 1. BUILDING (5 Campus Buildings)
-- ============================================================================
INSERT INTO building (building_name, location, description) VALUES
('Vivekananda Academic Block', 'North Campus, Sector A', 'Main undergraduate lecture halls, auditorium, and faculty chambers'),
('Sir C.V. Raman Science Complex', 'West Campus, Sector B', 'Physics, Chemistry, and Advanced Materials research laboratories'),
('Dr. A.P.J. Abdul Kalam Tech Center', 'East Campus, Sector C', 'Computer Science labs, high-performance computing cluster, and server rooms'),
('Rabindranath Tagore Central Library', 'Central Campus, Sector A', 'Four-floor campus library, digital archives, and quiet study carrels'),
('Gargi Student Residence Block A', 'South Campus, Sector D', 'Undergraduate student residence hall with dining commons');

-- ============================================================================
-- 2. ROOM (15 Campus Rooms across Buildings)
-- ============================================================================
INSERT INTO room (room_number, room_type, floor, building_id) VALUES
-- Building 1: Vivekananda Academic Block
('101', 'Lecture Hall', 1, 1),
('102', 'Smart Classroom', 1, 1),
('205', 'Seminar Hall', 2, 1),
('301', 'Faculty Lounge', 3, 1),

-- Building 2: Sir C.V. Raman Science Complex
('L-101', 'Organic Chemistry Lab', 1, 2),
('L-202', 'Laser Optics Lab', 2, 2),
('L-204', 'Instrumentation Lab', 2, 2),

-- Building 3: Tech Center
('CS-101', 'Network & Systems Lab', 1, 3),
('CS-201', 'AI Research Lab', 2, 3),
('DC-01', 'Campus Data Center', 0, 3),

-- Building 4: Central Library
('LIB-101', 'Circulation & Reading Room', 1, 4),
('LIB-202', 'Digital Media Lab', 2, 4),

-- Building 5: Residence Block A
('H-104', 'Dormitory Room', 1, 5),
('H-210', 'Dormitory Room', 2, 5),
('H-COMMON', 'Common Room & Mess', 1, 5);

-- ============================================================================
-- 3. ASSET (10 Physical Equipment Assets)
-- ============================================================================
INSERT INTO asset (asset_name, asset_type, brand_model, install_date, room_id, status) VALUES
('Split Air Conditioner 2.0 Ton', 'HVAC', 'Daikin FTKF60TV', '2023-04-15', 2, 'Active'),
('High-Lumen Overhead Projector', 'Audio-Visual', 'Epson EB-2250U', '2023-01-10', 1, 'Active'),
('Fume Hood Extraction System', 'Lab Equipment', 'Esco Frontier Acela', '2022-08-20', 5, 'Active'),
('Precision Chiller Unit', 'HVAC', 'Blue Star CWF50', '2023-03-05', 6, 'Active'),
('48-Port Managed Core Switch', 'Network & IT', 'Cisco Catalyst 9300', '2022-11-12', 10, 'Active'),
('Commercial Precision Rack AC', 'HVAC', 'Schneider Uniflair', '2022-11-15', 10, 'Active'),
('Heavy-Duty Water Booster Pump', 'Plumbing', 'Grundfos CMBE 5-62', '2021-06-18', 15, 'Active'),
('Interactive Smart Whiteboard', 'Audio-Visual', 'Samsung Flip Pro 75"', '2023-07-22', 3, 'Active'),
('Ceiling Cassette Fan 60W', 'Electrical', 'Havells Stealth Air', '2023-02-14', 11, 'Active'),
('Industrial Exhaust Blower', 'HVAC', 'Crompton Greaves 2HP', '2022-05-10', 7, 'Active');

-- ============================================================================
-- 4. ROLE (4 Access Roles)
-- ============================================================================
INSERT INTO role (role_name, description) VALUES
('Student', 'Registered campus student with service request logging permissions'),
('Faculty', 'Teaching and research faculty members with priority submission access'),
('Staff', 'Departmental administrative and laboratory operational personnel'),
('Facility Manager', 'Operations director overseeing triage, assignments, closures, and budgeting');

-- ============================================================================
-- 5. USER (8 Campus Community Users)
-- ============================================================================
INSERT INTO "user" (full_name, email, phone, role_id, status) VALUES
('Dr. Ramesh Sundaram', 'ramesh.sundaram@campus.edu', '+91 98765 43210', 2, 'Active'),
('Prof. Ananya Sen', 'ananya.sen@campus.edu', '+91 98765 43211', 2, 'Active'),
('Vikramaditya Roy', 'vikram.roy@campus.edu', '+91 98765 43212', 1, 'Active'),
('Priya Sharma', 'priya.sharma@campus.edu', '+91 98765 43213', 1, 'Active'),
('Manohar Lal (Lab Tech)', 'manohar.lal@campus.edu', '+91 98765 43214', 3, 'Active'),
('Sunita Kulkarni (Warden)', 'sunita.k@campus.edu', '+91 98765 43215', 3, 'Active'),
('Col. Rajesh Nair (Retd)', 'rajesh.nair@campus.edu', '+91 98765 43216', 4, 'Active'),
('Amitav Ghosh', 'amitav.ghosh@campus.edu', '+91 98765 43217', 1, 'Active');

-- ============================================================================
-- 6. CATEGORY (6 Maintenance Categories)
-- ============================================================================
INSERT INTO category (category_name, description) VALUES
('Electrical', 'Wiring faults, lighting, circuit breakers, power outlets, and switches'),
('Plumbing', 'Water supply, pipe leakages, drainage, washroom fixtures, and pumps'),
('HVAC', 'Heating, air conditioning, refrigeration, and ventilation ducts'),
('Carpentry & Civil', 'Doors, window glazing, locks, furniture, masonry, and ceiling tiles'),
('Network & IT Infrastructure', 'Data cabling, patch panels, rack power, and display mounts'),
('Laboratory Utilities', 'Gas piping, fume extraction, vacuum lines, and pure water taps');

-- ============================================================================
-- 7. PRIORITY (4 SLA Classifications)
-- ============================================================================
INSERT INTO priority (priority_level, description, response_time_hr) VALUES
('Critical', 'Severe emergency affecting campus safety, data centers, or essential services', 2),
('High', 'Significant disruption to teaching, laboratory sessions, or water/power supply', 8),
('Medium', 'Operational defect with workarounds available; scheduled within 1 business day', 24),
('Low', 'Minor cosmetic or preventive defect; scheduled within regular weekly cycles', 72);

-- ============================================================================
-- 8. STATUS (5 Lifecycle Stages)
-- ============================================================================
INSERT INTO status (status_name, description) VALUES
('Open', 'Request registered and queued for management triage and review'),
('Assigned', 'Technician designated and work order dispatched'),
('In Progress', 'Active diagnosis, repair, or procurement underway by assigned technician'),
('On Hold', 'Repair temporarily suspended awaiting parts, specialized tools, or access'),
('Closed', 'Work verified complete, resolution documented, and sign-off recorded');

-- ============================================================================
-- 9. TECHNICIAN (6 Internal Technical Staff across all operational categories)
-- ============================================================================
INSERT INTO technician (full_name, phone, email, department, status, labor_rate) VALUES
('Mahesh Chandra', '+91 98200 11221', 'mahesh.tech@campus.edu', 'Electrical Maintenance', 'Active', 350.00),
('Dinesh Kumar Verma', '+91 98200 11222', 'dinesh.tech@campus.edu', 'Plumbing & Hydraulics', 'Active', 300.00),
('Gurpreet Singh', '+91 98200 11223', 'gurpreet.tech@campus.edu', 'HVAC & Refrigeration', 'Active', 420.00),
('Arunachalam P.', '+91 98200 11224', 'arun.tech@campus.edu', 'Civil & Carpentry', 'Active', 280.00),
('Nadeem Akhtar', '+91 98200 11225', 'nadeem.tech@campus.edu', 'Network Infrastructure', 'Active', 450.00),
('Suresh Patil', '+91 98200 11226', 'suresh.tech@campus.edu', 'Laboratory Utilities', 'Active', 350.00);

-- ============================================================================
-- 10. MATERIAL (10 Inventory Items)
-- ============================================================================
INSERT INTO material (material_name, unit, unit_cost, stock_qty, status) VALUES
('Philips 20W T8 LED Tube Light', 'Piece', 180.00, 150, 'Active'),
('Havells 16A Single Pole MCB', 'Piece', 240.00, 80, 'Active'),
('Astral 1-inch CPVC Pipe (3m length)', 'Length', 380.00, 45, 'Active'),
('1/2-inch Brass Ball Valve', 'Piece', 290.00, 60, 'Active'),
('R-410A Eco Refrigerant Gas', 'Kg', 950.00, 30, 'Active'),
('D-Link Cat6 UTP Cable Box (305m)', 'Box', 6200.00, 12, 'Active'),
('Heavy-Duty Hydraulic Door Closer', 'Piece', 1250.00, 25, 'Active'),
('Washbasin Ceramic Tap Spindle', 'Piece', 140.00, 90, 'Active'),
('Thermal Overload Relay 10-16A', 'Piece', 850.00, 15, 'Active'),
('Acoustic Ceiling Mineral Board 2x2', 'Piece', 220.00, 100, 'Active');

-- ============================================================================
-- 11. REQUEST (10 Requests Across Statuses, Priorities, and Buildings)
-- ============================================================================
INSERT INTO request (
    request_number, request_date, description, category_id, priority_id,
    requested_by, room_id, asset_id, status_id, closed_date, resolution_description, closed_by
) VALUES
-- Request 1: Critical Closed Request with full closure details and feedback
('REQ-20260920-0001', '2026-09-20 08:30:00', 'Data Center precision AC unit throwing high-temperature alert E-04', 3, 1, 5, 10, 6, 5, '2026-09-20 11:15:00', 'Recharged 2.5 kg R410A refrigerant and cleaned condenser coils. Operating temperature restored to 19°C.', 7),

-- Request 2: High Closed Request
('REQ-20260921-0002', '2026-09-21 09:15:00', 'Water supply leak in ground floor common washroom flooding corridor', 2, 2, 6, 15, 7, 5, '2026-09-21 14:30:00', 'Replaced ruptured 1-inch CPVC union and installed new heavy-duty brass ball valve.', 7),

-- Request 3: Medium Closed Request
('REQ-20260922-0003', '2026-09-22 10:00:00', 'Overhead projector image flickers and shuts down randomly during lectures', 1, 3, 1, 1, 2, 5, '2026-09-23 11:00:00', 'Replaced faulty HDMI wall transceiver and tightened internal power rail connectors.', 7),

-- Request 4: High In-Progress Request
('REQ-20260925-0004', '2026-09-25 11:20:00', 'Organic Chemistry Lab fume hood extraction motor vibrating abnormally and making screeching noise', 3, 2, 2, 5, 3, 3, NULL, NULL, NULL),

-- Request 5: Medium In-Progress Request
('REQ-20260926-0005', '2026-09-26 14:00:00', 'Multiple ceiling LED tube lights dead in central library reading hall', 1, 3, 4, 11, 9, 3, NULL, NULL, NULL),

-- Request 6: Critical On-Hold Request (Waiting for replacement part)
('REQ-20260927-0006', '2026-09-27 08:00:00', 'High-current main breaker tripping intermittently under AC load in Lecture Hall 102', 1, 1, 1, 2, 1, 4, NULL, NULL, NULL),

-- Request 7: Low Assigned Request
('REQ-20260928-0007', '2026-09-28 10:30:00', 'Seminar hall entrance door slamming shut violently due to broken damper', 4, 4, 3, 3, NULL, 2, NULL, NULL, NULL),

-- Request 8: Low Open Request (Unassigned)
('REQ-20260929-0008', '2026-09-29 15:45:00', 'Loose floor tiles near faculty chamber entrance creating tripping hazard', 4, 4, 1, 4, NULL, 1, NULL, NULL, NULL),

-- Request 9: Medium Open Request (Unassigned)
('REQ-20260930-0009', '2026-09-30 09:00:00', 'Water tap in residence hall room 210 dripping continuously', 2, 3, 8, 14, NULL, 1, NULL, NULL, NULL),

-- Request 10: High Closed Request (Closed, awaiting optional feedback)
('REQ-20260930-0010', '2026-09-30 11:00:00', 'Core network switch port drops packets to AI Research lab workstations', 5, 2, 5, 9, 5, 5, '2026-09-30 16:30:00', 'Re-terminated degraded Cat6 patch line and configured secondary port redundancy.', 7);

-- ============================================================================
-- 12. ASSIGNMENT (Technician Assignments, including a Reassignment)
-- ============================================================================
INSERT INTO assignment (request_id, technician_id, assigned_date, due_date, status) VALUES
-- For Request 1 (Closed)
(1, 3, '2026-09-20 08:45:00', '2026-09-20 12:00:00', 'Completed'),

-- For Request 2 (Closed)
(2, 2, '2026-09-21 09:30:00', '2026-09-21 16:00:00', 'Completed'),

-- For Request 3 (Closed)
(3, 1, '2026-09-22 10:30:00', '2026-09-23 12:00:00', 'Completed'),

-- For Request 4 (In Progress)
(4, 3, '2026-09-25 11:45:00', '2026-09-26 12:00:00', 'In Progress'),

-- For Request 5 (In Progress)
(5, 1, '2026-09-26 14:30:00', '2026-09-27 18:00:00', 'In Progress'),

-- For Request 6 (On Hold - Original technician reassigned due to scope)
(6, 1, '2026-09-27 08:15:00', '2026-09-27 16:00:00', 'Reassigned'),
(6, 3, '2026-09-27 10:00:00', '2026-09-28 18:00:00', 'In Progress'),

-- For Request 7 (Assigned)
(7, 4, '2026-09-28 11:00:00', '2026-09-30 12:00:00', 'Assigned'),

-- For Request 10 (Closed)
(10, 5, '2026-09-30 11:30:00', '2026-09-30 18:00:00', 'Completed');

-- ============================================================================
-- 13. WORK_LOG (Labor Execution Records)
-- ============================================================================
INSERT INTO work_log (assignment_id, work_date, work_description, hours_spent) VALUES
-- Assignment 1 (Request 1 - AC Repair)
(1, '2026-09-20 09:00:00', 'Initial pressure test of Schneider precision unit. Found suction pressure down by 25 PSI.', 1.50),
(1, '2026-09-20 10:30:00', 'Injected UV dye, sealed service schrader valve, and completed refrigerant recharge. Test run successful.', 1.00),

-- Assignment 2 (Request 2 - Pipe Leak)
(2, '2026-09-21 10:00:00', 'Isolated vertical plumbing riser. Cut away cracked pipe section and prepared solvent weld surfaces.', 2.50),
(2, '2026-09-21 13:00:00', 'Installed replacement valve and verified line holding static mains pressure without weeping.', 1.50),

-- Assignment 3 (Request 3 - Projector)
(3, '2026-09-22 14:00:00', 'Dismounted projector, tested HDMI wall jack voltages, and cleaned dust filters.', 2.00),

-- Assignment 4 (Request 4 - Fume Hood)
(4, '2026-09-25 13:00:00', 'Opened extraction housing; bearing in motor housing exhibits excessive play. Lubricated shaft.', 3.00),

-- Assignment 5 (Request 5 - Library Lighting)
(5, '2026-09-26 15:30:00', 'Surveyed second floor fixtures. Identified 6 burnt-out ballast drivers and tubes.', 2.00),

-- Assignment 8 (Request 10 - Network Switch)
(8, '2026-09-30 12:00:00', 'Checked packet error rates via console. Re-crimped wall faceplate RJ45 connector and re-tested link.', 2.50);

-- ============================================================================
-- 14. WORK_LOG_MATERIAL (Materials Consumed During Work)
-- ============================================================================
INSERT INTO work_log_material (work_log_id, material_id, quantity_used, issued_date, issued_by) VALUES
-- Work Log 2: 2.5 kg R-410A gas for precision chiller
(2, 5, 2.50, '2026-09-20 10:15:00', 3),

-- Work Log 3: 1 CPVC pipe length for washroom leak
(3, 3, 1.00, '2026-09-21 09:45:00', 2),

-- Work Log 4: 1 Brass ball valve for washroom leak
(4, 4, 1.00, '2026-09-21 12:30:00', 2),

-- Work Log 6: 6 LED tube lights for Library
(6, 1, 6.00, '2026-09-26 15:00:00', 1);

-- ============================================================================
-- 15. STATUS_HISTORY (Complete Audit Trail of Status Transitions)
-- ============================================================================
INSERT INTO status_history (request_id, status_id, changed_by, changed_date, remarks) VALUES
-- Request 1 lifecycle: Open -> Assigned -> In Progress -> Closed
(1, 1, 5, '2026-09-20 08:30:00', 'Incident logged via student portal monitoring system'),
(1, 2, 7, '2026-09-20 08:45:00', 'Dispatched Gurpreet Singh for emergency HVAC inspection'),
(1, 3, 7, '2026-09-20 09:00:00', 'Technician on site; commencing diagnostics'),
(1, 5, 7, '2026-09-20 11:15:00', 'Closure approved after 30-min continuous load test without alarms'),

-- Request 2 lifecycle: Open -> Assigned -> In Progress -> Closed
(2, 1, 6, '2026-09-21 09:15:00', 'Hostel warden reported active leak flooding lobby'),
(2, 2, 7, '2026-09-21 09:30:00', 'Assigned Dinesh Kumar Verma (Plumber)'),
(2, 3, 7, '2026-09-21 10:00:00', 'Plumbing line isolated and repair started'),
(2, 5, 7, '2026-09-21 14:30:00', 'Pressure test passed, water restored, signed off by warden'),

-- Request 3 lifecycle: Open -> Assigned -> In Progress -> Closed
(3, 1, 1, '2026-09-22 10:00:00', 'Faculty reported recurring projector cutoff'),
(3, 2, 7, '2026-09-22 10:30:00', 'Assigned Mahesh Chandra (Electrician)'),
(3, 3, 7, '2026-09-22 14:00:00', 'Bench-testing projector input board'),
(3, 5, 7, '2026-09-23 11:00:00', 'Lecture room projector tested with test laptop stream; closed'),

-- Request 4 lifecycle: Open -> Assigned -> In Progress
(4, 1, 2, '2026-09-25 11:20:00', 'Lab manager filed work order for noisy fume hood'),
(4, 2, 7, '2026-09-25 11:45:00', 'Assigned Gurpreet Singh'),
(4, 3, 7, '2026-09-25 13:00:00', 'Motor shaft inspected; sourcing replacement bearing'),

-- Request 5 lifecycle: Open -> Assigned -> In Progress
(5, 1, 4, '2026-09-26 14:00:00', 'Student filed ticket for dim study lighting'),
(5, 2, 7, '2026-09-26 14:30:00', 'Assigned Mahesh Chandra'),
(5, 3, 7, '2026-09-26 15:30:00', 'Replacing tubes across aisles 3 and 4'),

-- Request 6 lifecycle: Open -> Assigned -> On Hold
(6, 1, 1, '2026-09-27 08:00:00', 'Breaker trip cut power to classroom AV rack'),
(6, 2, 7, '2026-09-27 08:15:00', 'Assigned Mahesh Chandra'),
(6, 4, 7, '2026-09-27 10:30:00', 'Placed on hold pending delivery of 63A 3-phase molded breaker'),

-- Request 7 lifecycle: Open -> Assigned
(7, 1, 3, '2026-09-28 10:30:00', 'Department staff reported slamming door'),
(7, 2, 7, '2026-09-28 11:00:00', 'Assigned Arunachalam P. for carpentry fitting'),

-- Request 8 & 9: Open
(8, 1, 1, '2026-09-29 15:45:00', 'Submitted ticket via student portal'),
(9, 1, 8, '2026-09-30 09:00:00', 'Hostel room dripping tap ticket logged'),

-- Request 10: Open -> Assigned -> In Progress -> Closed
(10, 1, 5, '2026-09-30 11:00:00', 'Network drop reported by lab tech'),
(10, 2, 7, '2026-09-30 11:30:00', 'Assigned Nadeem Akhtar'),
(10, 3, 7, '2026-09-30 12:00:00', 'Network analyzer testing patch drops'),
(10, 5, 7, '2026-09-30 16:30:00', 'Switch port verified clear of frame errors; closed');

-- ============================================================================
-- 16. COST (Single-Ledger Financial Entries for Requests)
-- ============================================================================
-- Note: In accordance with the project convention:
-- - Material expenditures are recorded as CostType 'Material' (Qty * UnitCost).
-- - Labor expenditures are recorded as CostType 'Labor' (Hours * LaborRate).
-- - Service/Contractor charges are recorded as CostType 'Service'.
-- - Miscellaneous supplies are recorded as CostType 'Miscellaneous'.
INSERT INTO cost (request_id, cost_type, amount, cost_date, description) VALUES
-- Request 1 Costs (Data Center AC)
-- Material: 2.5 kg * 950 = 2375.00
(1, 'Material', 2375.00, '2026-09-20 10:15:00', '2.5 kg R-410A Refrigerant cylinder draw'),
-- Labor: 2.5 hrs * 420 = 1050.00
(1, 'Labor', 1050.00, '2026-09-20 11:15:00', '2.5 technician hours (Gurpreet Singh @ ₹420/hr)'),
-- Service: Emergency technician priority dispatch surcharge
(1, 'Service', 500.00, '2026-09-20 11:15:00', 'Off-hours emergency precision AC diagnostic callout'),

-- Request 2 Costs (Washroom Pipe Leak)
-- Material: 1 CPVC pipe (380) + 1 Ball valve (290) = 670.00
(2, 'Material', 670.00, '2026-09-21 12:30:00', '1-inch CPVC pipe length and brass ball valve'),
-- Labor: 4.0 hrs * 300 = 1200.00
(2, 'Labor', 1200.00, '2026-09-21 14:30:00', '4.0 technician hours (Dinesh Verma @ ₹300/hr)'),
-- Miscellaneous: Solvent cement and teflon tape
(2, 'Miscellaneous', 150.00, '2026-09-21 14:30:00', 'CPVC heavy-duty solvent cement and teflon tape packs'),

-- Request 3 Costs (Projector Repair)
-- Labor: 2.0 hrs * 350 = 700.00
(3, 'Labor', 700.00, '2026-09-23 11:00:00', '2.0 technician hours (Mahesh Chandra @ ₹350/hr)'),
-- Service: External electronic calibration testing
(3, 'Service', 450.00, '2026-09-23 11:00:00', 'AV wall box digital signal integrity verification'),

-- Request 5 Costs (Library Lights in-progress)
-- Material: 6 LED tubes * 180 = 1080.00
(5, 'Material', 1080.00, '2026-09-26 15:00:00', '6x Philips 20W LED T8 tubes issued from central stores'),
-- Labor: 2.0 hrs * 350 = 700.00
(5, 'Labor', 700.00, '2026-09-26 17:30:00', '2.0 technician hours logged to date (Mahesh Chandra)'),

-- Request 10 Costs (Network Switch)
-- Labor: 2.5 hrs * 450 = 1125.00
(10, 'Labor', 1125.00, '2026-09-30 16:30:00', '2.5 technician hours (Nadeem Akhtar @ ₹450/hr)'),
-- Miscellaneous: Shielded Cat6 RJ45 modular jacks
(10, 'Miscellaneous', 120.00, '2026-09-30 16:30:00', 'Gold-plated RJ45 modular jacks and strain boot covers');

-- ============================================================================
-- 17. FEEDBACK (Requester Ratings on Closed Requests)
-- ============================================================================
INSERT INTO feedback (request_id, user_id, rating, comments, feedback_date) VALUES
-- Feedback on Request 1 by Lab Tech Manohar Lal
(1, 5, 5, 'Outstanding emergency response. The AC was back up before server inlet temperatures crossed safe thresholds.', '2026-09-20 14:00:00'),

-- Feedback on Request 2 by Warden Sunita Kulkarni
(2, 6, 4, 'Prompt resolution of the flooding issue. Corridor clean-up was also arranged quickly.', '2026-09-21 16:00:00'),

-- Feedback on Request 3 by Dr. Ramesh Sundaram
(3, 1, 5, 'Projector worked smoothly in my subsequent 3-hour lecture without a single visual stutter. Very satisfied.', '2026-09-23 15:30:00');
