"""Accounts. Identity only: everything a person writes about themselves lives in profiles."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, String, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.profile import Profile

# RFC 5321 limit on an email address used as a login identifier.
EMAIL_MAX_LENGTH = 254


class AuthProvider(StrEnum):
    """Ways to sign in. Only email codes exist today; Google is planned (ADR 0006)."""

    EMAIL = "email"
    GOOGLE = "google"


class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    # Deletion requested; the account is hard-deleted at deletion_scheduled_for.
    PENDING_DELETION = "pending_deletion"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'suspended', 'pending_deletion')", name="status_valid"
        ),
        CheckConstraint(f"char_length(email) <= {EMAIL_MAX_LENGTH}", name="email_length"),
    )

    # CITEXT makes uniqueness and lookups case-insensitive without lower() everywhere.
    email: Mapped[str] = mapped_column(CITEXT(), unique=True)
    status: Mapped[str] = mapped_column(
        String(32), default=UserStatus.ACTIVE, server_default=text(f"'{UserStatus.ACTIVE}'")
    )
    email_verified_at: Mapped[datetime | None]
    last_login_at: Mapped[datetime | None]
    # Consent captured when the account is created: 18+ by self-declaration (ADR 0009) and
    # terms acceptance. An account without age_confirmed_at confirms on its next sign-in.
    age_confirmed_at: Mapped[datetime | None]
    terms_accepted_at: Mapped[datetime | None]
    terms_version: Mapped[str | None] = mapped_column(String(32))
    # Soft delete: when deletion was requested, and when the hard-delete job removes the row.
    deleted_at: Mapped[datetime | None]
    deletion_scheduled_for: Mapped[datetime | None] = mapped_column(index=True)

    profile: Mapped[Profile | None] = relationship(back_populates="user", passive_deletes=True)
