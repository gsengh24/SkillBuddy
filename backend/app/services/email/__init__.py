"""Outgoing email. Sending happens only in background jobs, never inside an API request."""

from app.services.email.senders import (
    ConsoleEmailSender,
    EmailDeliveryError,
    EmailMessage,
    EmailSender,
    GmailApiEmailSender,
    SmtpEmailSender,
    build_email_sender,
)

__all__ = [
    "ConsoleEmailSender",
    "EmailDeliveryError",
    "EmailMessage",
    "EmailSender",
    "GmailApiEmailSender",
    "SmtpEmailSender",
    "build_email_sender",
]
