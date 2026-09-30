"""What a person says about themselves, plus the structure the system derives from it."""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class ProfileVisibility(StrEnum):
    # Visible to the matcher and to people who receive an intro. There is no public
    # directory: see ARCHITECTURE.md, section 8.
    MATCHABLE = "matchable"
    # Excluded from new matches; existing connections are unaffected.
    PAUSED = "paused"


class Profile(TimestampMixin, Base):
    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint(
            "visibility IN ('matchable', 'paused')",
            name="visibility_valid",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # The user's own words, kept verbatim forever; ``structured`` is re-derivable from it.
    raw_about_text: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    structured: Mapped[dict[str, Any]] = mapped_column(
        default=dict, server_default=text("'{}'::jsonb")
    )
    # IANA timezone name, e.g. "Asia/Kolkata".
    timezone: Mapped[str | None] = mapped_column(String(64))
    # BCP 47 language tags, e.g. ["en", "hi", "pa"].
    languages: Mapped[list[str]] = mapped_column(
        ARRAY(String(35)), default=list, server_default=text("'{}'::varchar[]")
    )
    visibility: Mapped[str] = mapped_column(
        String(32),
        default=ProfileVisibility.MATCHABLE,
        server_default=text(f"'{ProfileVisibility.MATCHABLE}'"),
    )

    user: Mapped[User] = relationship(back_populates="profile")
