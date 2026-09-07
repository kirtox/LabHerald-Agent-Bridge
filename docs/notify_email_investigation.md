# `notify_email` Investigation Findings & Porting Guide

Date: 2026-09-07
Source project: `Intel_WirelessCE_Avatar`

## Verified Findings

`services/ace/eval/reverify.py` is the module in the ACE evaluation pipeline that re-analyzes down-voted cases against an updated playbook and emails the results.

It uses a relative import:

```python
from . import notify_email
```

This implies `notify_email` was originally located in the same package:

```text
services/ace/eval/notify_email.py
```

This file does not exist in the source project's current working tree; search results show it is neither an untracked file nor one excluded by `.gitignore`. As a result, directly importing or running `reverify.py` today would likely fail due to the missing `notify_email` module.

## Git History

`notify_email.py` was committed to Git at these points:

| Commit | Date | Description |
| --- | --- | --- |
| `a3b1d92ca1dadb175eb187a36c9660225286bd30` | 2026-07-29 | `add notify email feature` — first SMTP implementation |
| `34bcb5046e13f7d36c4fc35fde7aad25ec1cd329` | 2026-07-29 | Added SMTP test CLI and env-based settings parsing |
| `39d871b8474ff828af946f7f7e48510f617f26cd` | 2026-08-05 | Added `send_html_to(...)` for use by reverify |
| `23aacd5ede9f56ffd785fb736fb041ffc6e30a5d` | 2026-08-12 | Adjusted send behavior when no attached log is present |

The original implementation can be restored from the source project:

```powershell
git show a3b1d92ca1dadb175eb187a36c9660225286bd30:services/ace/eval/notify_email.py
```

It's recommended to also review the last version that includes `send_html_to(...)`, rather than only restoring the initial version:

```powershell
git log --all -- services/ace/eval/notify_email.py
git show 39d871b8474ff828af946f7f7e48510f617f26cd:services/ace/eval/notify_email.py
```

## Email Feature Design

This feature is not Outlook automation, nor an external web API; it uses the Python standard library `smtplib` to connect directly to an SMTP relay.

Default transport settings:

| Item | Default |
| --- | --- |
| SMTP host | `smtp.intel.com` |
| SMTP port | `25` |
| TLS | `False` |
| SMTP authentication | None |
| Timeout | `20` seconds |
| Default sender | The Windows UPN obtained by running `whoami /upn`, otherwise `intelavatar-no-reply@intel.com` |

The original implementation uses:

```python
with smtplib.SMTP(smtp_host, int(smtp_port), timeout=timeout_sec) as client:
    if use_tls:
        client.starttls()
    if username:
        client.login(username, password or "")
    client.sendmail(sender_addr, recipients, msg.as_string())
```

The message body is built as `MIMEMultipart` with `MIMEText(..., "html", "utf-8")`. The `send_html_to(...)` function called by `reverify.py` additionally supports HTML attachments; the attachment data format is:

```python
[
    ("report.html", html_content.encode("utf-8"), "html"),
]
```

## Environment Variable Contract

The original `notify_email.py` defines the following settings. Passwords must never be written into code or committed; they should be injected by the deployment environment's secret/credential store.

| Environment variable | Purpose | Default |
| --- | --- | --- |
| `ACE_NOTIFY_TO` | Automatic notification recipients, comma- or semicolon-separated | None; notification is skipped when absent |
| `ACE_NOTIFY_CC` | CC recipients | None |
| `ACE_SMTP_FROM` | Sender | UPN, otherwise the no-reply address |
| `ACE_SMTP_HOST` | SMTP host | `smtp.intel.com` |
| `ACE_SMTP_PORT` | SMTP port | `25` |
| `ACE_SMTP_USE_TLS` | Whether to enable STARTTLS | `false` |
| `ACE_SMTP_USERNAME` | SMTP username | None |
| `ACE_SMTP_PASSWORD` | SMTP password | None |

## How `reverify.py` Calls It

`reverify_and_notify(...)`:

1. Loads the `downvotes_*.json` manifest produced by `build_downvote_manifest(...)`.
2. Groups down-voted cases across the Wi-Fi / Bluetooth namespaces by `submitted_by_email`.
3. Re-runs the ACE agent against the updated playbook for cases that have an attached log.
4. Generates a replay HTML for each case, written to `<runs_dir>/<run_stamp>/reverify/`.
5. Calls the following API to send one combined notification email:

```python
notify_email.send_html_to(
    to_list=to_list,
    subject=subject,
    html_body=body,
    attachments=attachments,
)
```

`REVERIFY_REDIRECT_TO` is a global recipient override used for testing. When set, every email that would otherwise go to a real user is redirected to the configured address instead. It should be set to `None` in production.

`FALLBACK_REDIRECT_TO` handles only two situations: the user's email could not be obtained/validated, or the SMTP send to the real recipient failed. It never overrides a valid recipient.

## Recommended Next Steps for LabHerald-Agent-Bridge

### 1. Decide the email domain boundary first

Do not scatter SMTP code across agents, routes, or workflows. Build a single `email_notifier` / `notify_email` transport module; the calling workflow decides recipients, content, and attachments, while the module is only responsible for building the message, validating settings, and transport.

Suggested public API:

```python
def send_html_to(
    *,
    to_list: list[str],
    subject: str,
    html_body: str,
    attachments: list[tuple[str, bytes, str]] | None = None,
) -> None:
    ...
```

### 2. Centralize configuration at the environment/deployment layer

Use environment variables or an existing configuration system to inject the SMTP host, port, TLS, sender, and auth info. Don't assume `smtp.intel.com` is reachable — only reuse it if LabHerald's deployment environment explicitly allows it and the network path is confirmed.

### 3. Implement MIME attachments and safety checks

Use `email.mime` or the newer `email.message.EmailMessage` to build the HTML body and attachments. Checks should include:

- Recipient list must not be empty.
- Basic email format validation.
- Attachment filenames must not contain path separators or control characters.
- Attachment size and total send size must be bounded.
- SMTP password is sourced only from a secret store, never logged.

### 4. Offer dry-run before allowing real sends

Provide a testable `dry_run=True` mode: produce a MIME/HTML preview and log the intended recipients, without opening an SMTP connection. Treat real sending as an explicitly enabled deployment capability.

### 5. Add tests with a replaceable transport

Unit tests should inject or mock the SMTP client, covering at minimum:

- HTML email is built correctly.
- CC and attachments are included correctly.
- TLS and auth settings are applied correctly.
- Empty recipient list is rejected.
- SMTP failures are logged by the caller and go through a fallback (if the product needs one).
- Dry-run never issues a network request.

### 6. If the goal is to restore the source project's functionality

The last working `notify_email.py` can be recovered from Git, then checked against actual module requirements to confirm `send_html_to(...)` and attachment MIME handling are complete. After restoring, first run an import smoke check:

```powershell
python -c "from services.ace.eval import reverify; print('import ok')"
```

Then run reverify once in dry-run mode; verify recipient routing and the generated HTML attachments before testing against the real SMTP relay.

## Open Decisions

1. Will LabHerald use the corporate SMTP relay, the Microsoft Graph API, or an existing notification service?
2. Should email be sent from a service account or the user's UPN?
3. Which workflows are allowed to send email? Is approval / rate limiting required?
4. Is it acceptable to send logs, analysis results, or other potentially sensitive attachments?
5. Who owns retry, alerting, and audit records for failed sends?
