"""
Logging Utility Module
Provides standardized logging configuration across backend components.
"""

from __future__ import annotations

import logging
import sys
from app.config import get_config


def setup_logging() -> None:
    """Initialize root logger formatting and level."""
    config = get_config()
    log_level = getattr(logging, config.log_level, logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance with standardized formatting."""
    return logging.getLogger(name)
