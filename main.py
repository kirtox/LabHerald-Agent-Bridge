"""
main.py
-------
Entry point for the UX Lab Admin Robot.

Usage
-----
# Run once immediately (good for testing):
    python main.py --run-now

# Start the interval scheduler (scans every SCAN_INTERVAL_MINUTES defined in config.json):
    python main.py

# Test individual pipeline stages:
    python main.py --test-step folder        # Step 1: check network folder access
    python main.py --test-step scan          # Step 2: scan for new archives (dry-run)
    python main.py --test-step avatar --archive <path>   # Step 3: run IntelAvatar on a specific archive
    python main.py --test-step email --archive <path>    # Step 4: generate draft + send email (pass a JSON path)

The scheduler keeps running until you press Ctrl-C.
"""

import argparse
import glob
import os
import sys
import time
from datetime import datetime

import schedule

from config import COMPLETED_FOLDER, LOCAL_STAGING_FOLDER, SCAN_INTERVAL_MINUTES, SOURCE_FOLDER, STATE_FILE, WARNING_FILE
from email_draft import send_via_outlook
from file_processor import process_archive, run_intel_avatar, wait_for_avatar_result, _copy_to_staging
from folder_watcher import check_folder_access, scan_new_archives
from logger_setup import setup_logger
from state_manager import clear_warning, load_processed, save_processed, save_warning

logger = setup_logger()


# ---------------------------------------------------------------------------
# Step-level test helpers
# ---------------------------------------------------------------------------

def test_folder() -> None:
    """Test Step 1: verify network folder is accessible."""
    logger.info(f"[TEST] Checking folder access: {SOURCE_FOLDER}")
    ok = check_folder_access(SOURCE_FOLDER)
    logger.info(f"[TEST] Result: {'OK' if ok else 'FAILED'}")


def test_scan() -> None:
    """Test Step 2: scan for new archives (read-only, no processing)."""
    logger.info("[TEST] Loading processed state...")
    processed = load_processed(STATE_FILE)
    logger.info(f"[TEST] Already processed: {len(processed)} file(s)")
    new_archives = scan_new_archives(SOURCE_FOLDER, processed)
    logger.info(f"[TEST] New archives found: {len(new_archives)}")
    for p in new_archives:
        logger.info(f"  {p}")


def test_copy() -> None:
    """Test Step 2.5: pick the first unprocessed archive from SOURCE_FOLDER and copy it to local staging."""
    processed = load_processed(STATE_FILE)
    new_archives = scan_new_archives(SOURCE_FOLDER, processed)
    if not new_archives:
        logger.info("[TEST] No unprocessed archives found in SOURCE_FOLDER.")
        return
    target = new_archives[0]
    logger.info(f"[TEST] Copying to local staging: {target}")
    local_path = _copy_to_staging(target)
    if local_path:
        logger.info(f"[TEST] Staged successfully: {local_path}")
    else:
        logger.error("[TEST] Copy to staging failed.")


def test_avatar() -> None:
    """Test Step 3: find the latest .zip in LOCAL_STAGING_FOLDER and run IntelAvatar on it."""
    zips = sorted(glob.glob(os.path.join(LOCAL_STAGING_FOLDER, "*.zip")), key=os.path.getmtime, reverse=True)
    if not zips:
        logger.error(f"[TEST] No .zip found in {LOCAL_STAGING_FOLDER}. Run --test-step copy first.")
        sys.exit(1)
    archive_path = zips[0]
    logger.info(f"[TEST] Sending to IntelAvatar: {archive_path}")
    ok = run_intel_avatar(archive_path)
    if not ok:
        logger.error("[TEST] IntelAvatar launch failed.")
        sys.exit(1)
    logger.info("[TEST] Waiting for result JSON...")
    result = wait_for_avatar_result(archive_path)
    if result:
        logger.info(f"[TEST] Result found: {result}")
    else:
        logger.error("[TEST] Timed out waiting for result.")


def test_email() -> None:
    """Test Step 4: find llm_report_*.json inside any extracted folder under LOCAL_STAGING_FOLDER."""
    matches = sorted(
        glob.glob(os.path.join(LOCAL_STAGING_FOLDER, "**", "llm_report_*.json"), recursive=True),
        key=os.path.getmtime,
        reverse=True,
    )
    if not matches:
        logger.error(f"[TEST] No llm_report_*.json found under {LOCAL_STAGING_FOLDER}. Run --test-step avatar first.")
        sys.exit(1)
    json_path = matches[0]
    logger.info(f"[TEST] Using result JSON: {json_path}")
    result_jsons = [json_path]
    logger.info("[TEST] Sending via Outlook...")
    send_via_outlook([json_path], COMPLETED_FOLDER, result_jsons)
    logger.info("[TEST] Email sent.")


# ---------------------------------------------------------------------------
# Core job
# ---------------------------------------------------------------------------

def run_scan_job() -> None:
    """One full scan-and-process cycle."""
    logger.info("=" * 60)
    logger.info(f"Scan job started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. Check folder access
    if not check_folder_access(SOURCE_FOLDER):
        logger.error("Source folder is not accessible. Aborting this run.")
        return

    # 2. Load previously processed filenames
    processed = load_processed(STATE_FILE)

    # 3. Find new archives
    new_archives = scan_new_archives(SOURCE_FOLDER, processed)

    if not new_archives:
        logger.info("Nothing to do. Scan complete.")
        return

    # 4. Process each archive
    successfully_processed: list[str] = []
    result_json_paths: list[str] = []
    for archive_path in new_archives:
        logger.info(f"Processing: {archive_path}")
        ok, reason, result_json = process_archive(archive_path)
        if ok:
            successfully_processed.append(archive_path)
            if result_json:
                result_json_paths.append(result_json)
            processed.add(archive_path.split("\\")[-1])  # store basename only
            save_processed(STATE_FILE, processed)         # persist after each success
            clear_warning(WARNING_FILE, archive_path.split("\\")[-1])
        else:
            logger.warning(f"Processing failed for: {archive_path} – reason: {reason}")
            save_warning(WARNING_FILE, archive_path.split("\\")[-1], reason)

    # 5. Send email via Outlook
    if successfully_processed:
        try:
            send_via_outlook(successfully_processed, COMPLETED_FOLDER, result_json_paths)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Could not send email via Outlook: {exc}")

    logger.info(
        f"Scan complete. {len(successfully_processed)}/{len(new_archives)} archive(s) processed successfully."
    )
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# Scheduler / CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="UX Lab Admin Robot – daily archive processor"
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Execute a single scan immediately and exit (skips the scheduler).",
    )
    parser.add_argument(
        "--test-step",
        choices=["folder", "scan", "copy", "avatar", "email"],
        metavar="STEP",
        help="Test a single pipeline stage and exit. Choices: folder, scan, copy, avatar, email",
    )
    args = parser.parse_args()

    # -- individual step tests --
    if args.test_step == "folder":
        test_folder()
        sys.exit(0)
    if args.test_step == "scan":
        test_scan()
        sys.exit(0)
    if args.test_step == "copy":
        test_copy()
        sys.exit(0)
    if args.test_step == "avatar":
        test_avatar()
        sys.exit(0)
    if args.test_step == "email":
        test_email()
        sys.exit(0)

    if args.run_now:
        logger.info("--run-now flag detected. Running immediately.")
        run_scan_job()
        sys.exit(0)

    # Interval scheduler
    logger.info(f"Scheduler started. Scanning every {SCAN_INTERVAL_MINUTES} minute(s).")
    logger.info("Press Ctrl-C to stop.")
    schedule.every(SCAN_INTERVAL_MINUTES).minutes.do(run_scan_job)

    # Run once at startup immediately
    logger.info("Running an initial scan on startup...")
    run_scan_job()

    _heartbeat_ticks = 0
    while True:
        schedule.run_pending()
        _heartbeat_ticks += 1
        if _heartbeat_ticks % 10 == 0:  # every ~5 minutes (10 x 30s)
            next_run = schedule.next_run()
            logger.info(f"[Scheduler] Waiting... next scan at {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        time.sleep(30)  # check every 30 seconds


if __name__ == "__main__":
    main()
