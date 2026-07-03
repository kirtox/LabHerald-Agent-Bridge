"""
file_processor.py
-----------------
Handles the full pipeline for each archive found in SOURCE_FOLDER:

  1. Copy archive from network share to local staging folder.
  2. Send local copy to IntelAvatar via --sendto.
  3. Wait for Avatar to write result.log into the extracted folder.
  4. Create /Completed/<archive-name>/ folder on the network share.
  5. Move the original archive from SOURCE_FOLDER into that folder.
  6. Copy result.log into the same Completed sub-folder.
  7. Clean up the local staging copy.
"""

import glob
import os
import shutil
import subprocess
import time

from config import (
    AVATAR_RESULT_PATTERN,
    COMPLETED_FOLDER,
    INTELAVATAR_LNK,
    INTELAVATAR_TIMEOUT,
    LOCAL_STAGING_FOLDER,
)
from logger_setup import setup_logger

logger = setup_logger()


def _ensure_dir(path: str) -> bool:
    """Create *path* (and parents) if it doesn't already exist."""
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError as exc:
        logger.error(f"Cannot create folder '{path}': {exc}")
        return False


def _copy_to_staging(source_archive: str) -> str | None:
    """
    Copy *source_archive* from the network share to LOCAL_STAGING_FOLDER.
    Returns the local path on success, None on failure.
    """
    if not _ensure_dir(LOCAL_STAGING_FOLDER):
        return None

    dest = os.path.join(LOCAL_STAGING_FOLDER, os.path.basename(source_archive))
    try:
        shutil.copy2(source_archive, dest)
        logger.info(f"Staged '{os.path.basename(source_archive)}' → {LOCAL_STAGING_FOLDER}")
        return dest
    except OSError as exc:
        logger.error(f"Failed to copy archive to staging: {exc}")
        return None


def run_intel_avatar(archive_path: str) -> bool:
    """
    Execute IntelAvatar via its .lnk shortcut:
        cmd /c start "" "<lnk>" --agent-zip "<archive_path>"

    Windows resolves the shortcut through cmd /c start.
    Returns True if the process exited with code 0, False otherwise.
    """
    if not os.path.exists(INTELAVATAR_LNK):
        logger.error(f"IntelAvatar shortcut not found: {INTELAVATAR_LNK}")
        return False

    cmd = ["cmd", "/c", "start", "", INTELAVATAR_LNK, "--agent-zip", archive_path, "--auto-llm"]
    logger.info(f"Running IntelAvatar for: {os.path.basename(archive_path)}")
    logger.debug(f"Command: {cmd}")

    try:
        result = subprocess.run(
            cmd,
            timeout=INTELAVATAR_TIMEOUT,
            check=False,
        )
        if result.returncode == 0:
            logger.info(f"IntelAvatar launched successfully for: {os.path.basename(archive_path)}")
            return True
        else:
            logger.warning(
                f"IntelAvatar exited with code {result.returncode} "
                f"for: {os.path.basename(archive_path)}"
            )
            return False
    except subprocess.TimeoutExpired:
        logger.error(
            f"IntelAvatar timed out after {INTELAVATAR_TIMEOUT}s "
            f"for: {os.path.basename(archive_path)}"
        )
        return False
    except OSError as exc:
        logger.error(f"Failed to launch IntelAvatar: {exc}")
        return False


def wait_for_avatar_result(local_archive: str, poll_interval: int = 5) -> str | None:
    """
    Block until Avatar writes a file matching AVATAR_RESULT_PATTERN into the
    extracted folder (same directory as *local_archive*, sub-folder named after
    the archive stem), or until INTELAVATAR_TIMEOUT seconds have elapsed.

    Returns the full path to the result file on success, None on timeout.
    """
    base_name = os.path.splitext(os.path.basename(local_archive))[0]
    extract_dir = os.path.join(os.path.dirname(local_archive), base_name)

    logger.info(f"Waiting for Avatar result in: {extract_dir}")
    logger.debug(f"Expecting pattern: {AVATAR_RESULT_PATTERN}")

    deadline = time.monotonic() + INTELAVATAR_TIMEOUT
    while time.monotonic() < deadline:
        matches = glob.glob(os.path.join(extract_dir, AVATAR_RESULT_PATTERN))
        if matches:
            result_file = matches[0]
            logger.info(f"Avatar result found: {result_file}")
            return result_file
        time.sleep(poll_interval)

    logger.error(
        f"Avatar result not found after {INTELAVATAR_TIMEOUT}s "
        f"for: {os.path.basename(local_archive)}"
    )
    return None


def collect_to_completed(source_archive: str, result_log: str) -> bool:
    """
    Create /Completed/<archive-stem>/ and move the original network archive
    plus the result.log into it.

    source_archive : original path on the network share (SOURCE_FOLDER)
    result_log     : local path to Avatar's result.log
    """
    archive_stem = os.path.splitext(os.path.basename(source_archive))[0]
    dest_folder = os.path.join(COMPLETED_FOLDER, archive_stem)

    if not _ensure_dir(dest_folder):
        return False

    # Move original archive into Completed/<archive-stem>/
    archive_dest = os.path.join(dest_folder, os.path.basename(source_archive))
    try:
        shutil.move(source_archive, archive_dest)
        logger.info(f"Moved archive → {dest_folder}\\")
    except OSError as exc:
        logger.error(f"Failed to move archive to Completed: {exc}")
        return False

    # Copy llm_report_*.json into Completed/<archive-stem>/ (keep original filename)
    result_dest = os.path.join(dest_folder, os.path.basename(result_log))
    try:
        shutil.copy2(result_log, result_dest)
        logger.info(f"Copied {os.path.basename(result_log)} → {dest_folder}\\")
    except OSError as exc:
        logger.error(f"Failed to copy result log to Completed: {exc}")
        return False

    return True


def process_archive(source_archive: str) -> tuple[bool, str, str | None]:
    """
    Full pipeline for a single archive:

      1. Copy from network share → local staging
      2. Run IntelAvatar --agent-zip <local copy>
      3. Wait for result.log
      4. Move original archive + result.log → Completed/<archive-stem>/
      5. Clean up local staging copy

    Returns (True, "", result_json_path) on success, or (False, reason, None) on failure.
    """
    archive_name = os.path.basename(source_archive)

    # Step 1 – stage locally
    local_archive = _copy_to_staging(source_archive)
    if not local_archive:
        return False, "Failed to copy archive to local staging", None

    try:
        # Step 2 – send to Avatar
        if not run_intel_avatar(local_archive):
            return False, "IntelAvatar failed to launch or returned non-zero exit code", None

        # Step 3 – wait for result.log
        result_log = wait_for_avatar_result(local_archive)
        if not result_log:
            return False, f"Avatar result ({AVATAR_RESULT_PATTERN}) not found within timeout ({INTELAVATAR_TIMEOUT}s)", None

        # Step 4 – collect to Completed on network share
        if not collect_to_completed(source_archive, result_log):
            return False, "Failed to move archive or copy result.log to Completed folder", None

        return True, "", result_log

    finally:
        # Step 5 – always clean up the local staging copy
        if os.path.exists(local_archive):
            try:
                os.remove(local_archive)
                logger.debug(f"Removed local staging copy: {local_archive}")
            except OSError as exc:
                logger.warning(f"Could not remove staging copy: {exc}")
