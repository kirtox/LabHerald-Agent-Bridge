# SMTP Email Pre-Launch Checklist

After completing the Outlook → SMTP migration ([docs/adr/0001-smtp-email-transport.md](./adr/0001-smtp-email-transport.md)), confirm the following items in order before going live.

## 1. Connectivity & Environment

- [ ] On the **machine that actually runs the schedule** (not your dev machine), run:
  ```powershell
  Test-NetConnection smtp.intel.com -Port 25
  ```
  Confirm `TcpTestSucceeded: True`. If `False`, that machine cannot reach the internal relay — switch to a reachable SMTP relay (`smtp_host` / `smtp_port` in `config.json`).

- [ ] Confirm whether `config.json`'s `email_from` (currently the placeholder `agent-admin-robot@intel.com`) is a sender address the corporate mail relay allows, to avoid being blocked as spoofing. If a different approved address is needed, update `email_from` directly.

- [ ] If the target relay requires authentication, fill in `smtp_username` / `smtp_password`; otherwise leave them as empty strings (no auth).

## 2. Dry-Run Verification (no email is actually sent)

- [ ] Set `email_dry_run` to `true` in `config.json`.
- [ ] Run:
  ```powershell
  python main.py --test-step email
  ```
- [ ] Check `logs/robot.log` and confirm the `[DRY RUN] Would send via ...` line has the correct `to` / `cc` / `subject` / content.

## 3. Real Send Verification

- [ ] Set `email_dry_run` back to `false`.
- [ ] It's recommended to temporarily change `email_to` to your own inbox (leave the production list untouched), then run `python main.py --test-step email` again to confirm the email actually arrives, the subject/content look correct, and the sender shows as `email_from` rather than a personal account.
- [ ] Once confirmed, restore `email_to` / `email_cc` to the production recipient list.

## 4. Packaging & Deployment

- [ ] Confirm `requirements.txt` no longer lists `pywin32`, then rebuild with `pyinstaller`:
  ```powershell
  pyinstaller --onefile --console --name LabHerald_Agent_Bridge --icon assets/icon.ico main.py
  ```
- [ ] When deploying to a target machine, make sure its `config.json` includes the new SMTP fields (`email_from` / `smtp_host` / `smtp_port` / `smtp_use_tls` / `smtp_username` / `smtp_password` / `email_dry_run`). If the target machine has an older `config.json` (missing these fields), the app will fall back to the defaults built into `config.py` (`smtp.intel.com:25`, no auth, `agent-admin-robot@intel.com`) — still worth confirming manually.

## 5. Post-Launch Monitoring

- [ ] After the first real scheduled run, check `logs/robot.log` for `Email sent via SMTP to: ...`, and watch for any `SMTP send failed` errors.
- [ ] Confirm recipients see the email's `From` as the fixed `email_from` address, not any personal account.

