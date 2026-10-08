"""Signup and access (A5): the signup mode, email domains, applications and invite codes.

None of this touches people who already have an account: it is checked only when a sign-in
would create one. With no rows at all, signups are open to any domain (today's behaviour).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models.user import EMAIL_MAX_LENGTH

SETTING_KEY_MAX_LENGTH = 64
DOMAIN_MAX_LENGTH = 253
INVITE_CODE_MIN_LENGTH = 4
INVITE_CODE_MAX_LENGTH = 32
INVITE_MAX_USES = 10_000


def _in(values: type[StrEnum]) -> str:
    return ", ".join(f"'{value.value}'" for value in values)


class SignupMode(StrEnum):
    OPEN = "open"
    INVITE_ONLY = "invite_only"
    CLOSED = "closed"


class DomainKind(StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"


class ApplicationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApplicationSource(StrEnum):
    """How they heard of the service: a fixed list, so no free text to moderate."""

    FRIEND = "friend"
    COLLEGE = "college"
    SOCIAL_MEDIA = "social_media"
    SEARCH = "search"
    EVENT = "event"
    OTHER = "other"


class AppSetting(Base):
    """One admin-set value, by key (``signup_mode`` here). A missing row means the default."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(SETTING_KEY_MAX_LENGTH), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # A plain id, like the audit log's actor: removing the admin changes nothing here.
    updated_by: Mapped[uuid.UUID | None]


class SignupDomain(UUIDPrimaryKeyMixin, Base):
    """An email domain new accounts may use (allowed) or may not (blocked). Exact match on
    the part after the last "@". An empty allow list means any domain; blocked wins."""

    __tablename__ = "signup_domains"
    __table_args__ = (
        UniqueConstraint("kind", "domain"),
        CheckConstraint(f"kind IN ({_in(DomainKind)})", name="kind_valid"),
        CheckConstraint(
            f"char_length(domain) BETWEEN 3 AND {DOMAIN_MAX_LENGTH} AND domain = lower(domain)",
            name="domain_valid",
        ),
    )

    kind: Mapped[str] = mapped_column(String(8))
    domain: Mapped[str] = mapped_column(String(DOMAIN_MAX_LENGTH))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    created_by: Mapped[uuid.UUID | None]


class SignupApplication(UUIDPrimaryKeyMixin, Base):
    """Someone asking to join while signups are invite only. No account exists until they
    sign in with a code sent to the address; approval lets that address create one.

    Deleted 90 days after a decision, or 180 days after applying if never decided.
    """

    __tablename__ = "signup_applications"
    __table_args__ = (
        CheckConstraint(f"status IN ({_in(ApplicationStatus)})", name="status_valid"),
        CheckConstraint(f"source IN ({_in(ApplicationSource)})", name="source_valid"),
        CheckConstraint(f"char_length(email) <= {EMAIL_MAX_LENGTH}", name="email_length"),
        # The approval queue and "Invite next 10": oldest pending first.
        Index("ix_signup_applications_status_created_at", "status", "created_at", "id"),
    )

    email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH), unique=True)
    source: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(
        String(16), default=ApplicationStatus.PENDING, server_default=text("'pending'")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    decided_at: Mapped[datetime | None]
    decided_by: Mapped[uuid.UUID | None]


class InviteCode(UUIDPrimaryKeyMixin, Base):
    """A code that lets new people join while signups are invite only.

    Admins create shareable codes with a use limit and an optional expiry. Approving an
    application makes a one-use code for that address only (``application_id`` set), which
    the invite email carries. Codes are upper case and compared that way.
    """

    __tablename__ = "invite_codes"
    __table_args__ = (
        CheckConstraint(
            f"max_uses BETWEEN 1 AND {INVITE_MAX_USES} AND uses >= 0 AND uses <= max_uses",
            name="uses_valid",
        ),
        CheckConstraint(
            f"char_length(code) BETWEEN {INVITE_CODE_MIN_LENGTH} AND {INVITE_CODE_MAX_LENGTH} "
            "AND code = upper(code)",
            name="code_valid",
        ),
        # The admin list: shareable codes, newest first.
        Index("ix_invite_codes_created_at_id", "created_at", "id"),
    )

    code: Mapped[str] = mapped_column(String(INVITE_CODE_MAX_LENGTH), unique=True)
    max_uses: Mapped[int]
    uses: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    expires_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    created_by: Mapped[uuid.UUID | None]
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("signup_applications.id", ondelete="CASCADE"), index=True
    )
