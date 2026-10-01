"""Email normalisation and the keyed hashes used for login codes and email addresses."""

from __future__ import annotations

from typing import Final

from app.core.config import Settings
from app.core.security import keyed_hash

OTP_DIGITS: Final = 6


def normalise_email(email: str) -> str:
    """The canonical form used for lookups, hashing and rate-limit keys."""
    return email.strip().lower()


def otp_hash(settings: Settings, email: str, code: str) -> str:
    """HMAC of a login code, bound to the address it was sent to."""
    return keyed_hash(settings.secret_key, "otp", f"{email}:{code}")


def email_hash(settings: Settings, email: str) -> str:
    """HMAC of an email address, for rate-limit keys and the audit log."""
    return keyed_hash(settings.secret_key, "email", email)
