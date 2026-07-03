# UX Lab Admin Robot — Workflow Overview

## Project Overview

UX Lab Admin Robot is an automation script that scans a network shared folder for archive files daily, sends them to IntelAvatar for analysis, moves the results into the `Completed` folder, and sends an email notification via Outlook.

---

## File Structure

```
UX_lab_admin_robot/
├── main.py              # Entry point: CLI parsing + scheduler
├── config.py            # Centralized path and parameter configuration
├── folder_watcher.py    # Folder access check + new archive scanner
├── file_processor.py    # Full processing pipeline for a single archive
├── email_draft.py       # Sends email notification via Outlook COM
├── state_manager.py     # Persists processed records + failure warnings
├── logger_setup.py      # Shared logger (console + rotating file)
└── requirements.txt     # Dependencies (schedule)
```

---

## Usage

```powershell
# Run once immediately (for testing)
python main.py --run-now

# Start the daily scheduler (runs every day at SCAN_TIME defined in config.py)
python main.py
```

---

## Step-by-Step Testing

### Step 1 — Verify network folder access
```powershell
python main.py --test-step folder
```

### Step 2 — Scan for new archives (dry-run, no processing)
```powershell
python main.py --test-step scan
```

### Step 2.5 — Copy the first unprocessed archive to local staging
```powershell
python main.py --test-step copy
```
> Picks the first unprocessed `.zip` from `SOURCE_FOLDER` and copies it to `Agent_Bridge_Admin/`

### Step 3 — Run IntelAvatar on the latest .zip in Agent_Bridge_Admin
```powershell
python main.py --test-step avatar
```
> Picks the latest `.zip` from `Agent_Bridge_Admin/`, sends it to IntelAvatar, and waits for `llm_report_*.json`

### Step 4 — Find llm_report JSON, generate draft, and send email
```powershell
python main.py --test-step email
```
> Finds the latest `llm_report_*.json` in any sub-folder of `Agent_Bridge_Admin/`, generates a draft, and sends it via Outlook

---

## Main Flow Diagram

```
Start main.py
     │
     ├─[--run-now]──► run_scan_job() ──► Exit
     │
     └─[Scheduler mode]──► Run run_scan_job() immediately
                        │
                        └──► Repeats automatically every day at 12:00
```

---

## `run_scan_job()` Core Flow

```
run_scan_job()
│
├─ 1. check_folder_access(SOURCE_FOLDER)
│       └─ If inaccessible → log error, abort this run
│
├─ 2. load_processed(STATE_FILE)
│       └─ Load already-processed filenames from processed_files.json
│
├─ 3. scan_new_archives(SOURCE_FOLDER, processed)
│       ├─ Match against ARCHIVE_PATTERN (^report_\d{8}_\d{6}\.zip$)
│       └─ Exclude already-processed files → return list of new archives
│
├─ 4. Run process_archive(archive_path) for each new archive
│       ├─ Success → add to processed set, save to STATE_FILE, clear warning record
│       └─ Failure → log warning, write to warning_files.json
│
└─ 5. send_via_outlook(successfully_processed, COMPLETED_FOLDER)
        └─ Send email notification via Outlook COM
```

---

## `process_archive()` Pipeline Details

| Step | Action | Failure Behavior |
|------|--------|-----------------|
| **1** | Copy archive from network share to local staging folder (`~/Downloads/Agent_Bridge_Admin/`) | Returns `(False, "Failed to copy archive to local staging")` |
| **2** | Send local archive to IntelAvatar via shortcut (`.lnk`) with `--agent-zip <path> --auto-llm` | Returns `(False, "IntelAvatar failed...")` |
| **3** | Poll until Avatar writes `llm_report_*.json` into the extracted folder (timeout: 1800 s) | Returns `(False, "Avatar result not found within timeout")` |
| **4** | Create `Completed/<archive-stem>/` on the network share, move the original archive and copy `llm_report_*.json` into it | Returns `(False, "Failed to move archive...")` |
| **5** | Always clean up the local staging copy regardless of outcome | Logs a warning only, does not interrupt the flow |

---

## State Management

### `processed_files.json`
Tracks all successfully processed archive filenames to prevent re-processing.

```json
{
  "processed": [
    "report_20260514_170256.zip",
    "report_20260515_093012.zip"
  ]
}
```

### `warning_files.json`
Records failed archives and their failure reasons, with cumulative failure count tracking. Cleared automatically upon successful processing.

```json
{
  "warnings": [
    {
      "archive": "report_20260516_110000.zip",
      "reason": "IntelAvatar failed to launch or returned non-zero exit code",
      "last_failed": "2026-06-29 12:00:05",
      "fail_count": 2
    }
  ]
}
```

---

## Configuration Parameters (`config.py`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `SOURCE_FOLDER` | `\\ger.corp.intel.com\...\UX_lab_logs` | Source network share path |
| `COMPLETED_FOLDER` | `SOURCE_FOLDER\Completed` | Completed files destination path |
| `INTELAVATAR_LNK` | `C:\Users\erniewux\...\IntelAvatar.lnk` | IntelAvatar shortcut path |
| `ARCHIVE_PATTERN` | `^report_\d{8}_\d{6}\.zip$` | Archive filename pattern (regex) |
| `SCAN_TIME` | `"12:00"` | Daily scheduler time (24-hour format) |
| `INTELAVATAR_TIMEOUT` | `1800` (seconds) | Maximum wait time for Avatar analysis |
| `LOCAL_STAGING_FOLDER` | `~/Downloads/Agent_Bridge_Admin` | Local staging folder |
| `EMAIL_TO` | `["recipient@intel.com"]` | Recipient list (multiple allowed) |
| `EMAIL_CC` | `["cc1@intel.com", ...]` | CC recipient list |
| `STATE_FILE` | `processed_files.json` | Processed files record |
| `WARNING_FILE` | `warning_files.json` | Failure warning record |

---

## Log Output

- **Console**: INFO level and above
- **File**: `logs/robot.log` (DEBUG level and above, rotating: max 5 MB, 3 backups)

---

## Email Notification

After successfully processing at least one archive, the system sends an email notification via Outlook COM automation.

The email includes:
- Scan date and time
- List of processed archives
- Link to the Completed folder
- IntelAvatar analysis summary (root cause + recommended actions)

Recipients and CC are configured in `config.py` via `EMAIL_TO` / `EMAIL_CC` — update those lists to change recipients.

> **Note**: Auto-send requires `pywin32` (`pip install pywin32`) and a signed-in Outlook desktop client on the machine.
