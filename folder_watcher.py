"""
folder_watcher.py
-----------------
Checks whether the source folder is accessible and scans it for new
archive files that match the expected naming pattern.
"""

import os
import re
import subprocess
from typing import List, Set

from config import ARCHIVE_PATTERN, NETWORK_PASSWORD, NETWORK_USERNAME
from logger_setup import setup_logger

logger = setup_logger()

_ARCHIVE_RE = re.compile(ARCHIVE_PATTERN)


def _mount_network_share(folder: str) -> None:
    """
    Use `net use` to authenticate against the UNC share if credentials are set.
    Extracts the share root (e.g. \\\\host\\share) from any sub-path.
    Does nothing if NETWORK_USERNAME is empty.
    """
    if not NETWORK_USERNAME:
        return
    # Derive the share root: \\host\share (first two UNC components)
    parts = folder.replace("/", "\\").lstrip("\\").split("\\")
    if len(parts) < 2:
        return
    share_root = "\\\\" + "\\".join(parts[:2])
    cmd = ["net", "use", share_root, f"/user:{NETWORK_USERNAME}", NETWORK_PASSWORD, "/persistent:no"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            logger.info(f"Network share authenticated: {share_root}")
        else:
            logger.warning(f"net use returned code {result.returncode}: {result.stderr.strip()}")
    except Exception as exc:
        logger.warning(f"net use failed: {exc}")


def check_folder_access(folder: str) -> bool:
    """
    Attempt to list the folder to verify access.
    Returns True if accessible, False otherwise.
    """
    _mount_network_share(folder)
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
