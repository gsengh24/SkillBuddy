"""Request and response models for authentication and the account endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import EMAIL_MAX_LENGTH, User

# Deliberately permissive: the real check is that the code arrives in that inbox.
EMAIL_PATTERN: Final = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=3, max_length=EMAIL_MAX_LENGTH, pattern=EMAIL_PATTERN
    ),
]
_REQUEST = ConfigDict(extra="forbid")


class OtpRequestIn(BaseModel):
    model_config = _REQUEST

    email: Email


class OtpRequestOut(BaseModel):
    """Identical for every address, so it reveals nothing about which accounts exist."""

    status: Literal["sent"] = "sent"
    message: str = "If that address can receive email, a sign-in code is on its way."
    expires_in_seconds: int


class OtpVerifyIn(BaseModel):
    model_config = _REQUEST

    email: Email
    code: str = Field(pattern=r"^\d{6}$", description="The 6-digit code from the email.")
    age_confirmed: bool = Field(
        default=False,
        description=(
            "Self-declaration that the user is 18 or older (ADR 0009). Must be true to create an "
            "account, and to sign in to an account that has no recorded age confirmation."
        ),
    )
    accept_terms: bool = Field(
        default=False, description="Required when creating an account: the user accepts the terms."
    )


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    created_at: datetime
    email_verified_at: datetime | None
    last_login_at: datetime | None
    terms_version: str | None
    terms_accepted_at: datetime | None
    is_moderator: bool = Field(
        default=False, description="May use the moderation page and /api/v1/moderation."
    )

    @classmethod
    def from_user(cls, user: User, *, is_moderator: bool = False) -> UserOut:
        return cls(
            id=user.id,
            email=user.email,
            created_at=user.created_at,
            email_verified_at=user.email_verified_at,
            last_login_at=user.last_login_at,
            terms_version=user.terms_version,
            terms_accepted_at=user.terms_accepted_at,
            is_moderator=is_moderator,
        )


class DeletionScheduledOut(BaseModel):
    status: Literal["pending_deletion"] = "pending_deletion"
    deletion_scheduled_for: datetime
    message: str = (
        "Your account is scheduled for permanent deletion and you have been signed out "
        "everywhere. Your data is removed on the scheduled date."
    )


class AuthMethodsOut(BaseModel):
    """Which sign-in methods this server offers, so clients show only what works."""

    email_code: bool = True
    google: bool
    google_domains: list[str] = Field(
        description="Email domains Google sign-in accepts (empty when Google is off)."
    )


# A path on this site, never another origin: "/profile" yes, "//evil.example" or "https://..." no.
NEXT_PATH_PATTERN: Final = (
    r"^/([A-Za-z0-9\-._~!$&'()*+,;=:@%?][A-Za-z0-9\-._~!$&'()*+,;=:@%/?]{0,198})?$"
)


class GoogleStartIn(BaseModel):
    model_config = _REQUEST

    age_confirmed: bool = Field(
        default=False,
        description="As for /otp/verify: required for a new account or one without a recorded "
        "age confirmation (ADR 0009). Checked when Google sends the person back.",
    )
    accept_terms: bool = Field(default=False, description="Required when creating an account.")
    next: str | None = Field(
        default=None,
        pattern=NEXT_PATH_PATTERN,
        description="Path on this site to return to after signing in (default /home).",
    )


class GoogleStartOut(BaseModel):
    authorization_url: str = Field(description="Send the browser here (Google's sign-in page).")
