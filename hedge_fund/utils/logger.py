"""
Structured logging for the trading system.
"""

import logging
import sys
import os
from datetime import datetime


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Create a structured logger with console and optional file output."""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    fmt = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console.setFormatter(fmt)
    logger.addHandler(console)

    # File handler (optional, graceful fallback)
    log_dir = os.environ.get('HF_LOG_DIR',
                              os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs'))
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f'{datetime.now():%Y%m%d}.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    except (PermissionError, OSError):
        # Can't write log file — console-only logging
        pass

    return logger
