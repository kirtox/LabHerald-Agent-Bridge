# LabHerald Agent Bridge — Workflow Overview

## Project Overview

LabHerald Agent Bridge is an automation script that scans a network shared folder for archive files daily, sends them to IntelAvatar for analysis, moves the results into the `Completed` folder, and sends an email notification via SMTP.

---

## File Structure

```
LabHerald-Agent-Bridge/
├── main.py              # Entry point: CLI parsing + scheduler
├── config.py            # Centralized path and parameter configuration
├── folder_watcher.py    # Folder access check + new archive scanner
├── file_processor.py    # Full processing pipeline for a single archive
├── email_draft.py       # Builds the notification email (HTML body)
├── notify_email.py      # Sends email via SMTP relay (see docs/adr/0001-smtp-email-transport.md)
├── state_manager.py     # Persists processed records + failure warnings
├── logger_setup.py      # Shared logger (console + rotating file)
└── requirements.txt     # Dependencies (schedule, pytest)
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
> Finds the latest `llm_report_*.json` in any sub-folder of `Agent_Bridge_Admin/`, generates a draft, and sends it via SMTP

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
└─ 5. send_via_smtp(successfully_processed, COMPLETED_FOLDER)
        └─ Send email notification via SMTP relay
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
| `EMAIL_FROM` | `"agent-admin-robot@intel.com"` | Fixed sender address (never the running user's identity) |
| `SMTP_HOST` / `SMTP_PORT` | `"smtp.intel.com"` / `25` | SMTP relay address |
| `SMTP_USE_TLS` | `false` | Whether to call STARTTLS before sending |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | `""` / `""` | Optional SMTP auth; left blank when the relay doesn't require login |
| `EMAIL_DRY_RUN` | `false` | When `true`, logs the email instead of sending it |
| `STATE_FILE` | `processed_files.json` | Processed files record |
| `WARNING_FILE` | `warning_files.json` | Failure warning record |

---

## Packaging as EXE (PyInstaller)

### Install PyInstaller
```powershell
pip install pyinstaller
```

### Build
```powershell
pyinstaller --onefile --console --name LabHerald_Agent_Bridge --icon assets/icon.ico main.py
```

The EXE will be output to `dist\LabHerald_Agent_Bridge.exe`.

### Deploy
Copy the following files next to the EXE before running:
```
dist/
├── LabHerald_Agent_Bridge.exe
├── config.json          ← edit this to change paths / settings
```

> **Note**: `config.json` is auto-generated with default values on first run if it is missing.
> `processed_files.json`, `warning_files.json`, and `logs/` are also created automatically next to the EXE.

---

## Log Output

- **Console**: INFO level and above
- **File**: `logs/robot.log` (DEBUG level and above, rotating: max 5 MB, 3 backups)

---

## Email Notification

After successfully processing at least one archive, the system sends an email notification via a direct SMTP relay connection (see `notify_email.py` and `docs/adr/0001-smtp-email-transport.md`).

The email includes:
- Scan date and time
- List of processed archives
- Link to the Completed folder
- IntelAvatar analysis summary (root cause + recommended actions)

Recipients and CC are configured in `config.py` via `EMAIL_TO` / `EMAIL_CC` — update those lists to change recipients. Sender address and SMTP relay settings are configured in `config.json` (`email_from`, `smtp_host`, `smtp_port`, `smtp_use_tls`, `smtp_username`, `smtp_password`, `email_dry_run`).

> **Note**: The sender is always the fixed `email_from` address — it does not depend on which Windows account runs the scheduler, and no local mail client is required.
