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


class AuthProvider(StrEnum):
    EMAIL = "email"
    GOOGLE = "google"


class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("auth_provider IN ('email', 'google')", name="auth_provider_valid"),
        CheckConstraint("status IN ('active', 'suspended', 'deleted')", name="status_valid"),
    )

    # CITEXT makes uniqueness and lookups case-insensitive without lower() everywhere.
    email: Mapped[str] = mapped_column(CITEXT(), unique=True)
    auth_provider: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(
        String(32), default=UserStatus.ACTIVE, server_default=text(f"'{UserStatus.ACTIVE}'")
    )
    email_verified_at: Mapped[datetime | None]
    # Soft delete marker; a scheduled job hard-deletes within the legal retention window.
    deleted_at: Mapped[datetime | None]

    profile: Mapped[Profile | None] = relationship(back_populates="user", passive_deletes=True)
