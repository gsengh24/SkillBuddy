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
    default_message = "To create an account, accept the terms."


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
