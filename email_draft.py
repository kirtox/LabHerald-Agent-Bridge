"""
email_draft.py
--------------
Builds the processed-archive notification email and sends it via the SMTP
transport in notify_email.py.
"""

import json
import os
from datetime import datetime
from typing import List

from config import EMAIL_CC, EMAIL_TO
from logger_setup import setup_logger
import notify_email

logger = setup_logger()


def _parse_report(json_path: str) -> dict:
    """Extract issue_time, root_cause_summary, and recommended_actions from a llm_report JSON."""
    try:
        with open(json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return {
            "issue_time": data.get("issue_time", "N/A"),
            "root_cause": data.get("report", {}).get("root_cause_summary", "N/A"),
            "actions": data.get("report", {}).get("recommended_actions", []),
        }
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(f"Could not parse report JSON '{json_path}': {exc}")
        return {}


def _build_analysis_section_html(result_json_paths: list[str]) -> str:
    """Build an HTML analysis block from one or more llm_report JSON files."""
    if not result_json_paths:
        return ""
    html = "<hr><p><strong>IntelAvatar Analysis</strong></p>"
    for json_path in result_json_paths:
        parsed = _parse_report(json_path)
        if not parsed:
            continue
        archive_label = os.path.basename(os.path.dirname(json_path))
        html += f"<p><strong>[{archive_label}]</strong><br>"
        html += f"<strong>Issue Time</strong>&nbsp;&nbsp;: {parsed['issue_time']}<br>"
        html += f"<strong>Root Cause</strong>&nbsp;: {parsed['root_cause']}</p>"
        if parsed["actions"]:
            html += "<p><strong>Recommended Actions:</strong><ul>"
            for action in parsed["actions"]:
                html += f"<li>{action}</li>"
            html += "</ul></p>"
    html += "<hr>"
    return html


def _build_html_body(processed_files: List[str], completed_folder: str, result_json_paths: list[str] | None = None) -> str:
    """Build an HTML email body for Outlook (no .eml headers)."""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d %H:%M:%S")

    file_items = "".join(
        f"<li>{os.path.basename(p)}</li>" for p in processed_files
    ) if processed_files else "<li>(none)</li>"

    analysis_html = _build_analysis_section_html(result_json_paths or [])

    # Convert UNC path (\\server\share) to file URL (file:////server/share) for hyperlink
    folder_url = "file:////" + completed_folder.lstrip("\\").replace("\\", "/")

    return f"""\
        <html><body>
        <p><strong><span style="color:red;">
        TEST EMAIL – This is a test run of the Agent Admin Robot email notification.
        </span></strong></p>
        <p>Hi,</p>
        <p>The Agent Admin Robot completed a scan at <strong>{date_str}</strong> and processed the following archive(s):</p>
        <ul>{file_items}</ul>
        <p>All processed files have been moved to:</p>
        <ul><li><a href="{folder_url}">{completed_folder}</a></li></ul>
        {analysis_html}
        <p>Please review the IntelAvatar submissions in shared folder if needed.</p>
        <p>Best regards,<br>Agent Admin Robot</p>
        <hr>
        <p><strong><span style="color:red;">
        This is an automatically generated email. Please do not reply.
        </span></strong></p>
        </body></html>"""


def send_via_smtp(processed_files: List[str], completed_folder: str, result_json_paths: list[str] | None = None) -> None:
    """
    Build and send the processed-archive notification email via the SMTP
    transport in notify_email.py. Recipients and CC are configured in
    config.py (EMAIL_TO, EMAIL_CC); sender and relay settings come from
    config.json (see docs/adr/0001-smtp-email-transport.md).
    """
    subject = f"[Agent Admin Robot] TEST EMAIL – Processed Archives \u2013 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    html_body = _build_html_body(processed_files, completed_folder, result_json_paths)
    logger.debug(f"Email subject: {subject}")
    logger.debug(f"HTML body length: {len(html_body)} chars")

    notify_email.send_html_to(
        to_list=EMAIL_TO,
        subject=subject,
        html_body=html_body,
        cc_list=EMAIL_CC,
    )


if __name__ == "__main__":
    import sys
    from config import COMPLETED_FOLDER

    # Usage: python email_draft.py [path/to/llm_report_*.json ...]
    # If no args given, sends a dummy test email with no attachments.
    json_paths = sys.argv[1:]
    # Derive archive name from the parent folder of each JSON (e.g. report_20260624_005000)
    dummy_archives = [os.path.dirname(p) for p in json_paths] if json_paths else ["[test run – no archive]"]

    print(f"Sending via SMTP...")
    send_via_smtp(dummy_archives, COMPLETED_FOLDER, json_paths or None)
    print("Done.")
