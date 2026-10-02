"""Who may sign in: the domain allow-list, the address exceptions and the block list.

Shared by email codes and Google sign-in (ADR 0011). Every comparison is an exact match on
the normalised (lower-case) address or on the part after its last "@", so "thapar.edu"
admits neither "evilthapar.edu" nor "thapar.edu.example.com" nor "x.thapar.edu".
"""

from __future__ import annotations

from enum import StrEnum

from app.core.config import Settings
from app.services.auth.errors import EmailNotAllowedError


class SignInMethod(StrEnum):
    EMAIL_CODE = "email_code"
    GOOGLE = "google"


def email_domain(email: str) -> str:
    return email.rpartition("@")[2]


def is_email_allowed(settings: Settings, email: str, method: SignInMethod) -> bool:
    """``email`` must already be normalised (see ``normalise_email``)."""
    if email in settings.blocked_emails:
        return False
    domain = email_domain(email)
    if method is SignInMethod.GOOGLE:
        # Exceptions never apply to Google: it is for the allowed domains only.
        return domain in settings.allowed_email_domains
    if not settings.allowed_email_domains and not settings.allowed_emails:
        return True
    return domain in settings.allowed_email_domains or email in settings.allowed_emails


def ensure_email_allowed(settings: Settings, email: str, method: SignInMethod) -> None:
    if not is_email_allowed(settings, email, method):
        raise EmailNotAllowedError
