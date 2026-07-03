"""
logger_setup.py
---------------
Configures a shared logger that writes to both the console and a single
rotating log file (max 5 MB, up to 3 backups) under ./logs/.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


def setup_logger(name: str = "ux_lab_robot") -> logging.Logger:
    """Return (or create) the named logger.  Safe to call multiple times."""
    logger = logging.getLogger(name)

    # Only add handlers once
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    os.makedirs(_LOG_DIR, exist_ok=True)
    log_file = os.path.join(_LOG_DIR, "robot.log")

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler – 5 MB per file, keep 3 backups
    fh = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger
