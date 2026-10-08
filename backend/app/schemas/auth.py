"""Request and response models for authentication and the account endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import (
    EMAIL_MAX_LENGTH,
    ApplicationSource,
    SignupMode,
    User,
    UserSession,
    UserStatus,
)
from app.models.signup import INVITE_CODE_MAX_LENGTH
from app.services.auth.devices import describe_device

# Deliberately permissive: the real check is that the code arrives in that inbox.
EMAIL_PATTERN: Final = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=3, max_length=EMAIL_MAX_LENGTH, pattern=EMAIL_PATTERN
    ),
]
_REQUEST = ConfigDict(extra="forbid")
InviteCode = Annotated[
    str | None,
    Field(
        max_length=INVITE_CODE_MAX_LENGTH,
        description=(
            "Only when signups are invite only and this creates an account (A5); ignored "
            "otherwise. Not needed when the address's application was approved."
        ),
    ),
]


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
    invite_code: InviteCode = None


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    created_at: datetime
    email_verified_at: datetime | None
    last_login_at: datetime | None
    terms_version: str | None
    terms_accepted_at: datetime | None
    status: Literal["active", "paused"] = Field(
        default="active",
        description="`paused`: hidden from matching and new intros; chats and sign-in carry on.",
    )
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
            # Only signed-in people read this, so the status is active or paused.
            status="paused" if user.status == UserStatus.PAUSED else "active",
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
    signup_mode: SignupMode = Field(
        default=SignupMode.OPEN,
        description=(
            "How new accounts are made (A5): `open`; `invite_only` (an invite code or an "
            "approved application); `closed`. Existing users can always sign in."
        ),
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
    invite_code: InviteCode = None


class GoogleStartOut(BaseModel):
    authorization_url: str = Field(description="Send the browser here (Google's sign-in page).")


class SessionOut(BaseModel):
    """A signed-in device. Never its IP address or the full user agent."""

    id: uuid.UUID
    device: str = Field(description='A short summary, e.g. "Chrome on Windows".')
    current: bool = Field(description="True for the device making this request.")
    created_at: datetime = Field(description="When this device signed in.")
    last_seen_at: datetime = Field(description="Last used (updated at most hourly).")

    @classmethod
    def from_session(cls, session: UserSession, *, current_id: uuid.UUID) -> SessionOut:
        return cls(
            id=session.id,
            device=describe_device(session.user_agent),
            current=session.id == current_id,
            created_at=session.created_at,
            last_seen_at=session.last_seen_at,
        )


class SessionList(BaseModel):
    items: list[SessionOut] = Field(description="Most recently used first.")


class ApplicationIn(BaseModel):
    """Ask to join while signups are invite only (A5)."""

    model_config = _REQUEST

    email: Email
    source: ApplicationSource = Field(description="How they heard of the service.")


class ApplicationReceivedOut(BaseModel):
    """Identical for every address, so it reveals nothing about who has applied."""

    status: Literal["received"] = "received"
