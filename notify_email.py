"""
notify_email.py
----------------
SMTP transport for outbound notification email.

Sends HTML email directly through an SMTP relay (stdlib smtplib), independent
of any locally installed mail client. This replaces the previous Outlook COM
automation, which leaked the identity of whichever user was logged into
Outlook on the machine running the scheduler.

All transport settings (relay host/port/TLS, optional auth, fixed sender,
dry-run switch) are read from config.py / config.json. See
docs/adr/0001-smtp-email-transport.md for why this module exists.
"""

import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import EMAIL_DRY_RUN, EMAIL_FROM, SMTP_HOST, SMTP_PORT, SMTP_PASSWORD, SMTP_USE_TLS, SMTP_USERNAME
from logger_setup import setup_logger

logger = setup_logger()


def send_html_to(
    *,
    to_list: list[str],
    subject: str,
    html_body: str,
    cc_list: list[str] | None = None,
    attachments: list[tuple[str, bytes, str]] | None = None,
) -> None:
    """
    Send an HTML email via the configured SMTP relay. The sender is always the
    fixed service address from config.json (EMAIL_FROM) — never the identity
    of the account running this process.

    attachments: optional list of (filename, raw_bytes, mime_subtype) tuples,
    e.g. ("report.html", b"...", "html"). Reserved for future use; not
    exercised by any caller today.

    When config.json sets "email_dry_run": true, the email is logged instead
    of sent — no SMTP connection is made.

    Raises ValueError if to_list is empty, or the underlying smtplib exception
    if the send fails. Callers are expected to catch and log.
    """
    if not to_list:
        raise ValueError("to_list is empty - refusing to send an email with no recipients")

    cc = cc_list or []
    recipients = list(to_list) + list(cc)

    body = MIMEMultipart("alternative")
    body.attach(MIMEText(html_body, "html", "utf-8"))

    if attachments:
        msg: MIMEMultipart = MIMEMultipart("mixed")
        msg.attach(body)
        for fname, raw, subtype in attachments:
            part = MIMEApplication(raw, _subtype=subtype or "octet-stream")
            part.add_header("Content-Disposition", "attachment", filename=fname)
            msg.attach(part)
    else:
        msg = body

    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = "; ".join(to_list)
    if cc:
        msg["Cc"] = "; ".join(cc)

    if EMAIL_DRY_RUN:
        attachment_names = [name for name, _, _ in attachments] if attachments else []
        logger.info(
            f"[DRY RUN] Would send via {SMTP_HOST}:{SMTP_PORT} from={EMAIL_FROM} "
            f"to={to_list} cc={cc} subject={subject!r} attachments={attachment_names}"
        )
        return

    logger.debug(f"Connecting to SMTP relay {SMTP_HOST}:{SMTP_PORT} (tls={SMTP_USE_TLS})...")
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as client:
            if SMTP_USE_TLS:
                client.starttls()
            if SMTP_USERNAME:
                client.login(SMTP_USERNAME, SMTP_PASSWORD or "")
            client.sendmail(EMAIL_FROM, recipients, msg.as_string())
    except Exception as exc:
        logger.error(f"SMTP send failed via {SMTP_HOST}:{SMTP_PORT} - {exc}")
        raise

    logger.info(f"Email sent via SMTP to: {', '.join(to_list)}" + (f" (cc: {', '.join(cc)})" if cc else ""))


if __name__ == "__main__":
    from datetime import datetime

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Sending SMTP test email via {SMTP_HOST}:{SMTP_PORT} (dry_run={EMAIL_DRY_RUN})...")
    send_html_to(
        to_list=[EMAIL_FROM],
        subject=f"[LabHerald] SMTP transport test - {now}",
        html_body=f"<html><body><p>SMTP transport test at {now}.</p></body></html>",
    )
    print("Done.")
