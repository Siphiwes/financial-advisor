"""Transactional email delivery using an explicitly configured SMTP relay."""

import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import get_setting

logger = logging.getLogger(__name__)


class EmailConfigurationError(ValueError):
    """Raised when outbound email is not configured."""


class EmailDeliveryError(RuntimeError):
    """Raised when the SMTP relay rejects or cannot deliver a message."""


def send_account_email(*, recipient: str, subject: str, text_body: str, html_body: str) -> None:
    """Send a transactional message over authenticated TLS SMTP."""
    enabled = (get_setting("EMAIL_ENABLED", "false") or "false").strip().casefold()
    if enabled not in {"1", "true", "yes", "on"}:
        raise EmailConfigurationError("Transactional email is disabled.")

    host = get_setting("SMTP_HOST")
    username = get_setting("SMTP_USERNAME")
    password = get_setting("SMTP_PASSWORD")
    sender = get_setting("SMTP_FROM_EMAIL")
    sender_name = get_setting("SMTP_FROM_NAME", "Financial Advisor") or "Financial Advisor"
    raw_port = get_setting("SMTP_PORT", "465") or "465"

    if not all((host, username, password, sender)):
        raise EmailConfigurationError("SMTP settings are incomplete.")
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise EmailConfigurationError("SMTP_PORT must be 465 or 587.") from exc
    if port not in {465, 587}:
        raise EmailConfigurationError("Only implicit TLS (465) or STARTTLS (587) is supported.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{sender_name} <{sender}>"
    message["To"] = recipient
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    try:
        context = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15, context=context) as server:
                server.login(username, password)
                server.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(username, password)
                server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        logger.warning("Transactional email delivery failed: %s", type(exc).__name__)
        raise EmailDeliveryError("The account email could not be delivered.") from exc
