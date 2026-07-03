"""
state_manager.py
----------------
Persists the set of already-processed filenames to a JSON file so that
the robot never submits the same archive twice, even across restarts.

Also manages warning_files.json which records failed archives and reasons.
"""

import json
import os
from datetime import datetime
from typing import Set

from logger_setup import setup_logger

logger = setup_logger()


def load_processed(state_file: str) -> Set[str]:
    """Load the set of previously processed filenames from *state_file*."""
    if not os.path.exists(state_file):
        logger.debug("State file not found – starting with empty set.")
        return set()

    try:
        with open(state_file, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        processed = set(data.get("processed", []))
        logger.debug(f"Loaded {len(processed)} processed filename(s) from state.")
        return processed
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"Could not read state file ({exc}). Starting fresh.")
        return set()


def save_processed(state_file: str, processed: Set[str]) -> None:
    """Persist *processed* filenames back to *state_file*."""
    try:
        with open(state_file, "w", encoding="utf-8") as fh:
            json.dump({"processed": sorted(processed)}, fh, indent=2)
        logger.debug(f"State saved – {len(processed)} processed filename(s).")
    except OSError as exc:
        logger.error(f"Failed to save state file: {exc}")


# ---------------------------------------------------------------------------
# Warning file helpers
# ---------------------------------------------------------------------------

def load_warnings(warning_file: str) -> list:
    """Load the list of warning records from *warning_file*."""
    if not os.path.exists(warning_file):
        return []
    try:
        with open(warning_file, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("warnings", [])
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"Could not read warning file ({exc}). Starting fresh.")
        return []


def save_warning(warning_file: str, archive_name: str, reason: str) -> None:
    """Append a failure record for *archive_name* to *warning_file*."""
    warnings = load_warnings(warning_file)

    # Update existing entry if this archive was already recorded
    for entry in warnings:
        if entry.get("archive") == archive_name:
            entry["reason"] = reason
            entry["last_failed"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            entry["fail_count"] = entry.get("fail_count", 1) + 1
            break
    else:
        warnings.append({
            "archive": archive_name,
            "reason": reason,
            "last_failed": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "fail_count": 1,
        })

    try:
        with open(warning_file, "w", encoding="utf-8") as fh:
            json.dump({"warnings": warnings}, fh, indent=2, ensure_ascii=False)
        logger.debug(f"Warning recorded for: {archive_name}")
    except OSError as exc:
        logger.error(f"Failed to save warning file: {exc}")


def clear_warning(warning_file: str, archive_name: str) -> None:
    """Remove the warning entry for *archive_name* once it succeeds."""
    warnings = load_warnings(warning_file)
    updated = [e for e in warnings if e.get("archive") != archive_name]
    if len(updated) == len(warnings):
        return  # nothing to remove
    try:
        with open(warning_file, "w", encoding="utf-8") as fh:
            json.dump({"warnings": updated}, fh, indent=2, ensure_ascii=False)
        logger.debug(f"Cleared warning for: {archive_name}")
    except OSError as exc:
        logger.error(f"Failed to update warning file: {exc}")
