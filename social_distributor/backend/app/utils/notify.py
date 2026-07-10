"""Outbound notifications for publish failures.

Best-effort: missing credentials silently skip the channel. We never raise
into the caller because the original failure already produced an audit log
and a retry/cancel state — a notification glitch shouldn't block recovery.
"""
from __future__ import annotations

import logging
from typing import Iterable

from ..config import config

log = logging.getLogger(__name__)


def send_failure_email(*, to: Iterable[str], subject: str, body: str) -> None:
    api_key = config.sendgrid_api_key
    sender = config.notify_email_from
    recipients = [r for r in to if r]
    if not (api_key and sender and recipients):
        return
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
    except ImportError:
        log.warning("sendgrid not installed; skipping email notification")
        return
    try:
        message = Mail(
            from_email=sender,
            to_emails=list(recipients),
            subject=subject,
            plain_text_content=body,
        )
        SendGridAPIClient(api_key).send(message)
    except Exception as exc:
        log.warning("failed to send sendgrid email: %s", exc)


def send_failure_sms(*, to: Iterable[str], body: str) -> None:
    sid = config.twilio_account_sid
    token = config.twilio_auth_token
    sender = config.twilio_from_number
    recipients = [r for r in to if r]
    if not (sid and token and sender and recipients):
        return
    try:
        from twilio.rest import Client
    except ImportError:
        log.warning("twilio not installed; skipping sms notification")
        return
    try:
        client = Client(sid, token)
        for recipient in recipients:
            client.messages.create(body=body, from_=sender, to=recipient)
    except Exception as exc:
        log.warning("failed to send twilio sms: %s", exc)


def send_failure_line(*, body: str) -> None:
    token = config.line_channel_access_token
    admin_user_id = config.line_admin_user_id
    if not (token and admin_user_id):
        return
    try:
        import requests
    except ImportError:
        log.warning("requests not installed; skipping line notification")
        return
    try:
        requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"to": admin_user_id, "messages": [{"type": "text", "text": body[:1000]}]},
            timeout=10,
        )
    except Exception as exc:
        log.warning("failed to send line push: %s", exc)


def notify_publish_failed(
    *,
    user_email: str | None,
    user_phone: str | None,
    platform: str,
    handle: str,
    error: str,
    target_id: int,
) -> None:
    subject = f"[Distributor] {platform} publish failed for {handle}"
    body = (
        f"Target #{target_id} on {platform} ({handle}) failed.\n\n"
        f"Error: {error}\n\n"
        f"Use the dashboard's status board to retry or cancel."
    )
    send_failure_email(to=[user_email] if user_email else [], subject=subject, body=body)
    send_failure_sms(to=[user_phone] if user_phone else [], body=f"{subject}: {error[:120]}")
    send_failure_line(body=f"⚠️ {subject}\n{error[:300]}")
