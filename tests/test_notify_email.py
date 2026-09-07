"""
tests/test_notify_email.py
---------------------------
Unit tests for the SMTP transport in notify_email.py. smtplib.SMTP is mocked
so no real network connection is ever made.
"""

from email import message_from_string
from unittest.mock import MagicMock, patch

import pytest

import notify_email


def _html_part_text(raw_message: str) -> str:
    """Decode the first text/html MIME part of a raw message string."""
    parsed = message_from_string(raw_message)
    for part in parsed.walk():
        if part.get_content_type() == "text/html":
            return part.get_payload(decode=True).decode("utf-8")
    raise AssertionError("no text/html part found")


@pytest.fixture(autouse=True)
def _reset_config(monkeypatch):
    """Pin transport config to known-good test values for every test."""
    monkeypatch.setattr(notify_email, "EMAIL_FROM", "robot@intel.com")
    monkeypatch.setattr(notify_email, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(notify_email, "SMTP_PORT", 25)
    monkeypatch.setattr(notify_email, "SMTP_USE_TLS", False)
    monkeypatch.setattr(notify_email, "SMTP_USERNAME", "")
    monkeypatch.setattr(notify_email, "SMTP_PASSWORD", "")
    monkeypatch.setattr(notify_email, "EMAIL_DRY_RUN", False)


def _mock_smtp_client():
    client = MagicMock()
    client.__enter__.return_value = client
    return client


@patch("notify_email.smtplib.SMTP")
def test_sends_html_email_to_recipients(mock_smtp_cls):
    client = _mock_smtp_client()
    mock_smtp_cls.return_value = client

    notify_email.send_html_to(
        to_list=["alice@intel.com"],
        subject="Test subject",
        html_body="<p>hello</p>",
    )

    mock_smtp_cls.assert_called_once_with("smtp.example.com", 25, timeout=20)
    client.sendmail.assert_called_once()
    sender, recipients, raw_message = client.sendmail.call_args[0]
    assert sender == "robot@intel.com"
    assert recipients == ["alice@intel.com"]
    assert "hello" in _html_part_text(raw_message)
    client.starttls.assert_not_called()
    client.login.assert_not_called()


@patch("notify_email.smtplib.SMTP")
def test_includes_cc_recipients(mock_smtp_cls):
    client = _mock_smtp_client()
    mock_smtp_cls.return_value = client

    notify_email.send_html_to(
        to_list=["alice@intel.com"],
        cc_list=["bob@intel.com"],
        subject="Test subject",
        html_body="<p>hello</p>",
    )

    _, recipients, raw_message = client.sendmail.call_args[0]
    assert recipients == ["alice@intel.com", "bob@intel.com"]
    assert "bob@intel.com" in raw_message


@patch("notify_email.smtplib.SMTP")
def test_uses_tls_and_auth_when_configured(mock_smtp_cls, monkeypatch):
    monkeypatch.setattr(notify_email, "SMTP_USE_TLS", True)
    monkeypatch.setattr(notify_email, "SMTP_USERNAME", "svc-user")
    monkeypatch.setattr(notify_email, "SMTP_PASSWORD", "svc-pass")
    client = _mock_smtp_client()
    mock_smtp_cls.return_value = client

    notify_email.send_html_to(
        to_list=["alice@intel.com"],
        subject="Test subject",
        html_body="<p>hello</p>",
    )

    client.starttls.assert_called_once()
    client.login.assert_called_once_with("svc-user", "svc-pass")


def test_empty_recipients_raises_without_connecting():
    with patch("notify_email.smtplib.SMTP") as mock_smtp_cls:
        with pytest.raises(ValueError):
            notify_email.send_html_to(to_list=[], subject="x", html_body="<p>x</p>")
        mock_smtp_cls.assert_not_called()


def test_dry_run_does_not_connect(monkeypatch):
    monkeypatch.setattr(notify_email, "EMAIL_DRY_RUN", True)
    with patch("notify_email.smtplib.SMTP") as mock_smtp_cls:
        notify_email.send_html_to(
            to_list=["alice@intel.com"],
            subject="Test subject",
            html_body="<p>hello</p>",
        )
        mock_smtp_cls.assert_not_called()


@patch("notify_email.smtplib.SMTP")
def test_attachments_included_as_mime_parts(mock_smtp_cls):
    client = _mock_smtp_client()
    mock_smtp_cls.return_value = client

    notify_email.send_html_to(
        to_list=["alice@intel.com"],
        subject="Test subject",
        html_body="<p>hello</p>",
        attachments=[("report.html", b"<p>report</p>", "html")],
    )

    _, _, raw_message = client.sendmail.call_args[0]
    assert "report.html" in raw_message
