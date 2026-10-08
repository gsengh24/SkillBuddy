"""The admin portal's tables (ADR 0015): roles and two-step login, admin sessions, audit log.

Owners come from ADMIN_OWNER_EMAILS, never from a row: a row's ``role`` is admin,
moderator, read-only, or null for an owner (whose row only holds their two-step setup).
The audit log is append-only: a database trigger refuses UPDATE and DELETE.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models.auth import DIGEST_LENGTH, IP_MAX_LENGTH

AUDIT_ACTION_MAX_LENGTH = 64
AUDIT_REASON_MIN_LENGTH = 10
AUDIT_REASON_MAX_LENGTH = 500


class AdminRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MODERATOR = "moderator"
    READONLY = "readonly"


# Roles a row may hold; owners come only from ADMIN_OWNER_EMAILS.
GRANTABLE_ROLES = (AdminRole.ADMIN, AdminRole.MODERATOR, AdminRole.READONLY)


class AdminAccount(Base):
    """Someone's admin role (null for owners) and two-step login set-up."""

    __tablename__ = "admin_accounts"
    __table_args__ = (
        CheckConstraint(
            "role IS NULL OR role IN ("
            + ", ".join(f"'{role.value}'" for role in GRANTABLE_ROLES)
            + ")",
            name="role_valid",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str | None] = mapped_column(String(16))
    # Who gave the role (an owner); no foreign key, so removing them changes nothing here.
    granted_by: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # The TOTP secret, encrypted with a key derived from SECRET_KEY. Set during setup;
    # ``two_step_enabled_at`` is set once a first code is confirmed.
    totp_secret: Mapped[str | None] = mapped_column(Text)
    two_step_enabled_at: Mapped[datetime | None]
    # The last time step accepted, so a code can't be used twice.
    last_totp_step: Mapped[int | None] = mapped_column(BigInteger)


class AdminRecoveryCode(UUIDPrimaryKeyMixin, Base):
    """Single-use codes for when the authenticator is lost. Only hashes are stored."""

    __tablename__ = "admin_recovery_codes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    code_hash: Mapped[str] = mapped_column(String(DIGEST_LENGTH), unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    used_at: Mapped[datetime | None]


class AdminSession(UUIDPrimaryKeyMixin, Base):
    """The second, short session an admin gets after the two-step code. Separate from the
    normal session; ends after ADMIN_SESSION_IDLE_MINUTES without use."""

    __tablename__ = "admin_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(DIGEST_LENGTH), unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(index=True)


class AdminAuditEntry(UUIDPrimaryKeyMixin, Base):
    """One thing an admin did. Append-only (a trigger refuses UPDATE and DELETE).

    The actor and target are plain ids, not foreign keys: deleting an account must never
    need to change the log. Reasons are kept here, never in application logs.
    """

    __tablename__ = "admin_audit_log"
    __table_args__ = (
        CheckConstraint(
            f"reason IS NULL OR char_length(reason) BETWEEN {AUDIT_REASON_MIN_LENGTH} "
            f"AND {AUDIT_REASON_MAX_LENGTH}",
            name="reason_length",
        ),
    )

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    actor_role: Mapped[str | None] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(AUDIT_ACTION_MAX_LENGTH), index=True)
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64), index=True)
    # Required for every change (at least 10 characters); null for sign-ins and the like.
    reason: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(String(IP_MAX_LENGTH))
