"""
folder_watcher.py
-----------------
Checks whether the source folder is accessible and scans it for new
archive files that match the expected naming pattern.
"""

import os
import re
from typing import List, Set

from config import ARCHIVE_PATTERN
from logger_setup import setup_logger

logger = setup_logger()

_ARCHIVE_RE = re.compile(ARCHIVE_PATTERN)


def check_folder_access(folder: str) -> bool:
    """
    Attempt to list the folder to verify access.
    Returns True if accessible, False otherwise.
    """
    try:
        os.listdir(folder)
        logger.info(f"Folder accessible: {folder}")
        return True
    except PermissionError:
        logger.error(f"Permission denied accessing folder: {folder}")
    except FileNotFoundError:
        logger.error(f"Folder not found: {folder}")
    except OSError as exc:
        logger.error(f"Cannot access folder '{folder}': {exc}")

    return False


def scan_new_archives(source_folder: str, processed: Set[str]) -> List[str]:
    """
    Scan *source_folder* and return a list of full paths to archive files
    whose basenames:
      - match ARCHIVE_PATTERN  (e.g. Report_20260514_170256.zip)
      - are not already in *processed*

    Returns an empty list when the folder is inaccessible or empty.
    """
    if not check_folder_access(source_folder):
        return []

    new_files: List[str] = []
    try:
        for entry in os.scandir(source_folder):
            if entry.is_file() and _ARCHIVE_RE.match(entry.name) and entry.name not in processed:
                new_files.append(entry.path)
    except OSError as exc:
        logger.error(f"Error while scanning folder: {exc}")
        return []

    if new_files:
        logger.info(f"Found {len(new_files)} new archive(s): {[os.path.basename(p) for p in new_files]}")
    else:
        logger.info("No new archives found.")

    return new_files
