# Campus Facility Maintenance Request Management System

Academic DBMS Project (#41) for managing campus maintenance requests (infrastructure, electrical, plumbing, HVAC, carpentry, and furniture) across university buildings and rooms.

---

## Architecture Overview

- **Database**: PostgreSQL 14+ (`campus_maintenance`) with a 17-table, 3NF-normalized relational schema enforcing relational integrity, constraints, indexes, views, and integrity triggers.
- **Backend Foundation**: Python 3.10+ layered architecture using `psycopg` 3 with robust connection pooling (`psycopg_pool`), environment-driven configuration (`python-dotenv`), repository pattern abstractions, and structured logging.

---

## Python Backend Foundation Setup

### 1. Prerequisites

- Python 3.10 or higher
- Running PostgreSQL server with the `campus_maintenance` database deployed
- (Optional) `uv` package installer or standard `pip`

### 2. Create the Python Virtual Environment

Using standard Python `venv`:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Or using `uv`:
```bash
uv venv
source .venv/bin/activate
```

### 3. Install Dependencies

Using `pip`:
```bash
pip install -r requirements.txt
```

Or using `uv`:
```bash
uv pip install -r requirements.txt
```

Dependencies include:
- `psycopg[binary,pool] >= 3.2.0` — Modern PostgreSQL driver with native connection pooling and binary extensions
- `python-dotenv >= 1.0.0` — Environment variable loader
- `pytest >= 8.0.0` — Test framework

### 4. Configure Environment Variables (`.env`)

Copy the template environment file:
```bash
cp .env.example .env
```

Edit `.env` to match your local PostgreSQL configuration:
```ini
# PostgreSQL Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=campus_maintenance
DB_USER=postgres
DB_PASSWORD=

# Connection Pooling Configuration
DB_POOL_MIN_SIZE=1
DB_POOL_MAX_SIZE=10
DB_POOL_TIMEOUT=30.0
DB_CONNECT_TIMEOUT=5

# Application Configuration
APP_ENV=development
APP_LOG_LEVEL=INFO
```

> **Security Note**: Never commit `.env` containing sensitive credentials to version control. The file is excluded via `.gitignore`.

### 5. Run Backend Diagnostics & Health Check

Verify connectivity, server metadata, and the 17 database tables:
```bash
python -m app.main
```

Expected diagnostic output:
```text
======================================================================
CAMPUS FACILITY MAINTENANCE REQUEST MANAGEMENT SYSTEM (Project #41)
Python Backend Foundation Diagnostics
======================================================================
Environment : development
Log Level   : INFO
DB Target   : localhost:5432/campus_maintenance (User: postgres)
----------------------------------------------------------------------
✓ Database Status      : HEALTHY
✓ Connected Database   : campus_maintenance
✓ Connected Role       : postgres
✓ PostgreSQL Version   : PostgreSQL 18.6 ...
✓ Public Tables Count  : 17 (Expected: 17)
✓ Connection Latency   : ~1-10 ms
======================================================================
Backend foundation initialized successfully.
```

### 6. Run the Test Suite

Execute the unit and integration test suite:
```bash
pytest -v
```

The test suite validates:
- Configuration parsing, defaults, bounds checking, and validation
- `psycopg` connection acquisition and simple query execution
- Connection pool recycling and leak prevention
- Transaction context management (`BEGIN ... COMMIT / ROLLBACK`)
- Repository primitives (`BaseRepository.fetch_one`, `BaseRepository.fetch_all`)
- Graceful connection failure handling on unreachable hosts/invalid credentials
