"""Authentication tables: identities, one-time codes, sessions and the audit log (ADR 0006).

Retention (storage rules, CLAUDE.md): OTP codes and sessions are purged once expired;
auth_events are pruned after a fixed number of days; everything for a user is removed by
the hard-delete job via ON DELETE CASCADE.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.signup import INVITE_CODE_MAX_LENGTH

# Column caps (storage rules): HMAC/SHA-256 hex digests, IPv6 text form, truncated UA.
DIGEST_LENGTH = 64
IP_MAX_LENGTH = 45
USER_AGENT_MAX_LENGTH = 256


class AuthIdentity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A way a user signs in. Email today; Google sign-in later adds provider='google'."""

    __tablename__ = "auth_identities"
    __table_args__ = (
        UniqueConstraint("provider", "subject"),
        CheckConstraint("provider IN ('email', 'google')", name="provider_valid"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(32))
    # Email: the normalised address. Google (later): the stable account id ("sub").
    subject: Mapped[str] = mapped_column(String(255))


class OtpCode(UUIDPrimaryKeyMixin, Base):
    """A one-time login code. Only an HMAC of the code is stored, never the code itself."""

    __tablename__ = "otp_codes"
    __table_args__ = (CheckConstraint("attempts >= 0", name="attempts_non_negative"),)

    email: Mapped[str] = mapped_column(CITEXT(), index=True)
    code_hash: Mapped[str] = mapped_column(String(DIGEST_LENGTH))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(index=True)
    attempts: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    consumed_at: Mapped[datetime | None]
    created_ip: Mapped[str | None] = mapped_column(String(IP_MAX_LENGTH))


class UserSession(UUIDPrimaryKeyMixin, Base):
    """A signed-in browser or device. The cookie holds the token; we store only its hash."""

    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(DIGEST_LENGTH), unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(index=True)
    user_agent: Mapped[str | None] = mapped_column(String(USER_AGENT_MAX_LENGTH))
    ip: Mapped[str | None] = mapped_column(String(IP_MAX_LENGTH))


class AuthEventType(StrEnum):
    OTP_REQUESTED = "otp_requested"
    OTP_FAILED = "otp_failed"
    OTP_LOCKED = "otp_locked"
    SIGNUP = "signup"
    LOGIN = "login"
    LOGIN_REFUSED = "login_refused"
    LOGOUT = "logout"
    LOGOUT_ALL = "logout_all"
    LOGOUT_OTHERS = "logout_others"
    SESSION_REVOKED = "session_revoked"
    ACCOUNT_PAUSED = "account_paused"
    ACCOUNT_RESUMED = "account_resumed"
    DELETION_REQUESTED = "deletion_requested"
    ACCOUNT_DELETED = "account_deleted"


AUTH_EVENT_TYPES_SQL = ", ".join(f"'{event.value}'" for event in AuthEventType)


class AuthEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only security audit log. A database trigger rejects UPDATEs."""

    __tablename__ = "auth_events"
    __table_args__ = (
        CheckConstraint(f"event_type IN ({AUTH_EVENT_TYPES_SQL})", name="event_type_valid"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(32))
    # HMAC of the email, so failed attempts can be correlated without storing the address.
    email_hash: Mapped[str | None] = mapped_column(String(DIGEST_LENGTH))
    ip: Mapped[str | None] = mapped_column(String(IP_MAX_LENGTH))
    user_agent: Mapped[str | None] = mapped_column(String(USER_AGENT_MAX_LENGTH))
    detail: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)


# Short paths only: the page to return to after Google sign-in, e.g. "/profile".
NEXT_PATH_MAX_LENGTH = 200


class OAuthState(UUIDPrimaryKeyMixin, Base):
    """One Google sign-in attempt (ADR 0011): single use, expires after a few minutes.

    Only an HMAC of the ``state`` value is stored. The nonce and PKCE verifier are derived
    from the state with the server's secret key, so neither is stored at all. The tick-box
    answers from the sign-in page travel here, so a first sign-in can create the account.
    """

    __tablename__ = "oauth_states"

    state_hash: Mapped[str] = mapped_column(String(DIGEST_LENGTH), unique=True)
    next_path: Mapped[str] = mapped_column(String(NEXT_PATH_MAX_LENGTH))
    age_confirmed: Mapped[bool]
    accept_terms: Mapped[bool]
    # An invite code typed on the sign-in page (A5), checked if this creates an account.
    invite_code: Mapped[str | None] = mapped_column(String(INVITE_CODE_MAX_LENGTH))
    created_ip: Mapped[str | None] = mapped_column(String(IP_MAX_LENGTH))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(index=True)
