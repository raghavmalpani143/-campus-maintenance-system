# Campus Facility Maintenance Request Management System

## Project Context
This is a DBMS academic project for managing campus maintenance requests (classrooms, electrical, plumbing, furniture, etc.).

## Current Status
- Review 1 ER diagram exists (to be located) and serves as the starting design.
- No database schema, DDL, or sample data has been created yet.
- The database is PostgreSQL with database name `campus_maintenance`.

## Development Rules (Review 2 Phase)
1. **Do not modify the database schema yet.**
2. **Do not create SQL yet.**
3. **Do not add unnecessary entities/features.**
4. First step: Inspect the existing Review 1 ER diagram and create a Review 2 audit of the current design.
5. The audit should cover:
   - 3NF normalization check
   - Functional dependencies
   - Data dictionary
   - Identification of needed constraints (PK, FK, UNIQUE, NOT NULL, CHECK, DEFAULT)
   - Unique request number generation
   - Closure details requirement
   - Non-negative material quantities and costs
   - Valid status transitions
   - Assignment control
   - Preparation for realistic sample data
   - Planning for SQL joins, aggregation, subqueries, and views
   - Reports pending requests, ageing, response time, technician load, building cost, material use, feedback

## Next Steps
After creating the Review 2 audit, await user approval before proceeding to schema creation and SQL implementation.