"""Errors the authentication endpoints can return (stable ``code`` values for clients)."""

from __future__ import annotations

from datetime import datetime
from http import HTTPStatus

from app.core.errors import AppError


class InvalidCodeError(AppError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "invalid_code"
    default_message = (
        "That code is incorrect or has expired. Check your latest email or request a new code."
    )


class CodeLockedError(AppError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "code_locked"
    default_message = "Too many incorrect attempts for this code. Request a new code."


class ConsentRequiredError(AppError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "consent_required"
    default_message = "To create an account, confirm that you are 18 or older and accept the terms."


class AccountPendingDeletionError(AppError):
    status_code = HTTPStatus.FORBIDDEN
    code = "account_pending_deletion"

    def __init__(self, scheduled_for: datetime | None) -> None:
        when = scheduled_for.date().isoformat() if scheduled_for else "soon"
        super().__init__(
            f"This account is scheduled for permanent deletion on {when} and can no longer "
            "sign in. Contact support if this is a mistake."
        )


class AccountSuspendedError(AppError):
    status_code = HTTPStatus.FORBIDDEN
    code = "account_suspended"
    default_message = "This account is suspended. Contact support for help."


class EmailNotAllowedError(AppError):
    """Outside the allowed domains or exceptions, or on the block list (ADR 0011)."""

    status_code = HTTPStatus.FORBIDDEN
    code = "email_not_allowed"
    default_message = "This email address can't be used to sign in here."


class GoogleSignInUnavailableError(AppError):
    status_code = HTTPStatus.NOT_FOUND
    code = "google_signin_unavailable"
    default_message = "Sign in with Google is not available."


class OAuthStateInvalidError(AppError):
    """Missing, expired, already used, or begun in another browser."""

    status_code = HTTPStatus.BAD_REQUEST
    code = "google_state_invalid"
    default_message = "That sign-in attempt has expired or was already used. Please try again."


class GoogleSignInCancelledError(AppError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "google_cancelled"
    default_message = "Google sign-in was cancelled."


class GoogleSignInFailedError(AppError):
    """Google's answer did not pass verification. Details go to the audit log only."""

    status_code = HTTPStatus.BAD_REQUEST
    code = "google_failed"
    default_message = "We couldn't sign you in with Google. Please try again or use an email code."
