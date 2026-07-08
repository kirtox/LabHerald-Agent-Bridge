"""
config.py
---------
Central configuration for UX Lab Admin Robot.
Settings are loaded from config.json (located next to the EXE or script).
If config.json does not exist, it will be created automatically with default values.
"""

import os
import sys
import json

# ---------------------------------------------------------------------------
# BASE_DIR — resolves correctly both as a .py script and as a PyInstaller EXE
# ---------------------------------------------------------------------------
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

# ---------------------------------------------------------------------------
# Default values — written to config.json on first run
# ---------------------------------------------------------------------------
_DEFAULTS: dict = {
    "source_folder_test": r"\\ger.corp.intel.com\ec\proj\ha\ICG\symstore\CMAttachments\JIRA\BT\Ernie\UX_lab_logs",
    "source_folder":      r"\\ger.corp.intel.com\ec\proj\ha\ICG\symstore\CMAttachments\JIRA\BT\UX_Lab_Logs",
    "intelavatar_lnk":    r"C:\Users\erniewux\AppData\Roaming\Microsoft\Windows\SendTo\IntelAvatar.lnk",
    "archive_pattern":    r"^report_\d{8}_\d{6}\.zip$",
    "email_to_test": [
        "steven1.chen@intel.com", "kj.fang@intel.com", "timdaway.lai@intel.com",
        "frank.fc.yang@intel.com", "erniex.wu@intel.com", "benx.lai@intel.com"
    ],
    "email_to": [
        "erniex.wu@intel.com"
    ],
    "email_cc": [
        "erniex.wu@intel.com"
    ],
    "scan_interval_minutes": 5,
    "intelavatar_timeout":   180,    "network_username":      "",
    "network_password":      "",    "avatar_result_pattern": "llm_report_*.json",
    "local_staging_folder":  "",   # leave empty to use ~/Downloads/Agent_Bridge_Admin
}

# ---------------------------------------------------------------------------
# Load config.json — create it with defaults if it doesn't exist
# ---------------------------------------------------------------------------
if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w", encoding="utf-8") as _f:
        json.dump(_DEFAULTS, _f, indent=4, ensure_ascii=False)
    _cfg = _DEFAULTS.copy()
else:
    with open(CONFIG_FILE, "r", encoding="utf-8") as _f:
        _cfg = json.load(_f)

# ---------------------------------------------------------------------------
# Expose constants — same names as before, no other files need to change
# ---------------------------------------------------------------------------
SOURCE_FOLDER_TEST = _cfg["source_folder_test"]
SOURCE_FOLDER      = _cfg["source_folder"]
COMPLETED_FOLDER   = SOURCE_FOLDER + r"\Completed"

INTELAVATAR_LNK  = _cfg["intelavatar_lnk"]
ARCHIVE_PATTERN  = _cfg["archive_pattern"]

STATE_FILE      = os.path.join(BASE_DIR, "processed_files.json")
EMAIL_DRAFT_DIR = BASE_DIR
WARNING_FILE    = os.path.join(BASE_DIR, "warning_files.json")

EMAIL_TO: list[str] = _cfg["email_to"]
EMAIL_CC: list[str] = _cfg["email_cc"]

SCAN_INTERVAL_MINUTES = int(_cfg.get("scan_interval_minutes", 60))
INTELAVATAR_TIMEOUT   = _cfg["intelavatar_timeout"]
NETWORK_USERNAME      = _cfg.get("network_username", "")
NETWORK_PASSWORD      = _cfg.get("network_password", "")
AVATAR_RESULT_PATTERN = _cfg["avatar_result_pattern"]

_staging = _cfg.get("local_staging_folder", "")
LOCAL_STAGING_FOLDER = (
    _staging if _staging
    else os.path.join(os.path.expanduser("~"), "Downloads", "Agent_Bridge_Admin")
)
