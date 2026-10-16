"""
Application Entry Point
Runs backend foundation initialization, configuration verification, and database health diagnosis.
"""

from __future__ import annotations

import sys
from app.config import get_config
from app.db import check_db_health, get_db_manager
from app.utils.logger import get_logger, setup_logging

logger = get_logger("app.main")


def run_diagnostics() -> bool:
    """Run backend foundation diagnostics and report status."""
    setup_logging()
    config = get_config()

    print("=" * 70)
    print("CAMPUS FACILITY MAINTENANCE REQUEST MANAGEMENT SYSTEM (Project #41)")
    print("Python Backend Foundation Diagnostics")
    print("=" * 70)
    print(f"Environment : {config.env}")
    print(f"Log Level   : {config.log_level}")
    print(f"DB Target   : {config.db.host}:{config.db.port}/{config.db.database} (User: {config.db.user})")
    print("-" * 70)

    health = check_db_health()

    if health.get("status") == "healthy":
        print("✓ Database Status      : HEALTHY")
        print(f"✓ Connected Database   : {health.get('database')}")
        print(f"✓ Connected Role       : {health.get('user')}")
        print(f"✓ PostgreSQL Version   : {health.get('server_version')}")
        print(f"✓ Public Tables Count  : {health.get('public_tables_count')} (Expected: 17)")
        print(f"✓ Connection Latency   : {health.get('latency_ms')} ms")
        print("=" * 70)
        print("Backend foundation initialized successfully.")
        get_db_manager().close_pool()
        return True
    else:
        print("✗ Database Status      : UNHEALTHY")
        print(f"✗ Error Message        : {health.get('error')}")
        print(f"✗ Latency              : {health.get('latency_ms')} ms")
        print("=" * 70)
        print("Backend foundation initialization failed.")
        get_db_manager().close_pool()
        return False


def main() -> None:
    """CLI execution entry point."""
    success = run_diagnostics()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
