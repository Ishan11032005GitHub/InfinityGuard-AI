from email.message import EmailMessage
import base64
import smtplib

import httpx

from ..config import get_settings


def _build_email(*, sender: str, recipient: str, subject: str, heading: str, message: str, action_url: str, action_label: str) -> EmailMessage:
    email = EmailMessage()
    email["From"] = sender
    email["To"] = recipient
    email["Subject"] = subject
    email.set_content(f"{heading}\n\n{message}\n\n{action_label}: {action_url}\n")
    email.add_alternative(
        f"""<!doctype html>
<html><body style="font-family:Arial,sans-serif;color:#111827">
  <h2>{heading}</h2>
  <p>{message}</p>
  <p><a href="{action_url}" style="background:#0f1720;color:white;padding:12px 18px;text-decoration:none;border-radius:6px">{action_label}</a></p>
  <p style="color:#64748b;font-size:12px">If you did not request this, you can ignore this email.</p>
</body></html>""",
        subtype="html",
    )
    return email


def _send_smtp(email: EmailMessage) -> bool:
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from_email:
        return False
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
        if settings.smtp_use_tls:
            client.starttls()
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password)
        client.send_message(email)
    return True


def _send_gmail_api(email: EmailMessage) -> bool:
    settings = get_settings()
    if not all([settings.gmail_client_id, settings.gmail_client_secret, settings.gmail_refresh_token, settings.gmail_from_email]):
        return False
    token_response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": settings.gmail_client_id,
            "client_secret": settings.gmail_client_secret,
            "refresh_token": settings.gmail_refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=10,
    )
    token_response.raise_for_status()
    access_token = token_response.json().get("access_token")
    if not access_token:
        return False
    raw_message = base64.urlsafe_b64encode(email.as_bytes()).decode()
    send_response = httpx.post(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"raw": raw_message},
        timeout=10,
    )
    send_response.raise_for_status()
    return True


def send_account_email(*, recipient: str, subject: str, heading: str, message: str, action_url: str, action_label: str) -> bool:
    settings = get_settings()
    provider = settings.email_provider.strip().lower()
    if provider == "gmail_api":
        email = _build_email(
            sender=settings.gmail_from_email,
            recipient=recipient,
            subject=subject,
            heading=heading,
            message=message,
            action_url=action_url,
            action_label=action_label,
        )
        return _send_gmail_api(email)
    email = _build_email(
        sender=settings.smtp_from_email,
        recipient=recipient,
        subject=subject,
        heading=heading,
        message=message,
        action_url=action_url,
        action_label=action_label,
    )
    return _send_smtp(email)
