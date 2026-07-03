"""
config.py
---------
Central configuration for UX Lab Admin Robot.
Edit the constants here to adjust paths, schedule time, and patterns.
"""

import os

# ---------------------------------------------------------------------------
# Network paths
# ---------------------------------------------------------------------------
SOURCE_FOLDER_TEST = r"\\ger.corp.intel.com\ec\proj\ha\ICG\symstore\CMAttachments\JIRA\BT\Ernie\UX_lab_logs"
SOURCE_FOLDER = r"\\ger.corp.intel.com\ec\proj\ha\ICG\symstore\CMAttachments\JIRA\BT\UX_Lab_Logs"
COMPLETED_FOLDER = SOURCE_FOLDER + r"\Completed"

# ---------------------------------------------------------------------------
# IntelAvatar shortcut path
# ---------------------------------------------------------------------------
INTELAVATAR_LNK = r"C:\Users\erniewux\AppData\Roaming\Microsoft\Windows\SendTo\IntelAvatar.lnk"

# ---------------------------------------------------------------------------
# Archive filename pattern  (e.g. report_20260514_170256.zip)
# ---------------------------------------------------------------------------
ARCHIVE_PATTERN = r"^report_\d{8}_\d{6}\.zip$"

# ---------------------------------------------------------------------------
# State file – tracks which archives have already been processed
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "processed_files.json")

# ---------------------------------------------------------------------------
# Email draft output directory (same folder as this script)
# ---------------------------------------------------------------------------
EMAIL_DRAFT_DIR = BASE_DIR

# ---------------------------------------------------------------------------
# Email recipients – edit these lists to change who gets notified
# ---------------------------------------------------------------------------
EMAIL_TO: list[str] = [
    "steven1.chen@intel.com", "kj.fang@intel.com", "timdaway.lai@intel.com", 
    "frank.fc.yang@intel.com", "erniex.wu@intel.com", "benx.lai@intel.com",
]
EMAIL_CC: list[str] = [
    "erniex.wu@intel.com",
]

# ---------------------------------------------------------------------------
# Scheduler – time of the daily scan (24-hour HH:MM)
# ---------------------------------------------------------------------------
SCAN_TIME = "12:00"

# Timeout (seconds) while waiting for IntelAvatar to finish per file
INTELAVATAR_TIMEOUT = 180

# Filename pattern that Avatar writes into the extracted folder when analysis is done
AVATAR_RESULT_PATTERN = "llm_report_*.json"

# Local staging folder – archives are copied here before being sent to Avatar
LOCAL_STAGING_FOLDER = os.path.join(os.path.expanduser("~"), "Downloads", "Agent_Bridge_Admin")

# Warning file – records archives that failed processing and their reasons
WARNING_FILE = os.path.join(BASE_DIR, "warning_files.json")
