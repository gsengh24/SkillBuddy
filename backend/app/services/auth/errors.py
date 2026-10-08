"""Errors the authentication endpoints can return (stable ``code`` values for clients)."""

from __future__ import annotations

from datetime import datetime
from http import HTTPStatus

from app.core.errors import AppError, ConflictError, NotFoundError


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


class AccountBannedError(AppError):
    status_code = HTTPStatus.FORBIDDEN
    code = "account_banned"
    default_message = "This account has been banned. Contact support if you think this is wrong."


class AccountPendingError(AppError):
    status_code = HTTPStatus.FORBIDDEN
    code = "account_pending"
    default_message = "Your account is waiting for approval. We'll email you when it's ready."


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


class SessionNotFoundError(NotFoundError):
    code = "session_not_found"
    default_message = "That device isn't signed in any more."


class CannotPauseError(ConflictError):
    code = "cannot_pause"
    default_message = "Only an active account can be paused."


class NotPausedError(ConflictError):
    code = "not_paused"
    default_message = "Your account isn't paused."


# --- Signup and access (A5): only new accounts; existing users always sign in -------------


class SignupsClosedError(AppError):
    status_code = HTTPStatus.FORBIDDEN
    code = "signups_closed"
    default_message = (
        "We're not taking new sign-ups right now. If you already have an account, sign in with "
        "the same email address."
    )


class InviteRequiredError(AppError):
    status_code = HTTPStatus.FORBIDDEN
    code = "invite_required"
    default_message = "Joining is by invite right now. Enter an invite code, or apply to join."


class InvalidInviteCodeError(AppError):
    status_code = HTTPStatus.FORBIDDEN
    code = "invalid_invite_code"
    default_message = "That invite code doesn't work. It may have expired or been used up."


class ApplicationsClosedError(ConflictError):
    code = "applications_closed"
    default_message = "Applications are only open while joining is by invite."
