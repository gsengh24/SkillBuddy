"""What a person says about themselves, plus the structure the system derives from it."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User

# Text caps (CLAUDE.md, storage rules). Enforced by the API schemas and by CHECKs.
ABOUT_TEXT_MAX_LENGTH = 2000
DISPLAY_NAME_MAX_LENGTH = 60
LINK_MAX_LENGTH = 200
MAX_LINKS = 3
MAX_LANGUAGES = 10


class ProfileVisibility(StrEnum):
    # Visible to the matcher and to people who receive an intro. There is no public
    # directory: see ARCHITECTURE.md, section 8.
    MATCHABLE = "matchable"
    # Excluded from new matches; existing connections are unaffected.
    PAUSED = "paused"


class ParseStatus(StrEnum):
    # No about text yet.
    EMPTY = "empty"
    # The text changed; a parse_profile job will (re)build ``structured``.
    PENDING = "pending"
    PARSED = "parsed"


class ParseSource(StrEnum):
    """Who produced ``structured``: an AI provider, the no-AI template, or the user's edit."""

    LLM = "llm"
    TEMPLATE = "template"
    USER = "user"


class Profile(TimestampMixin, Base):
    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint(
            "visibility IN ('matchable', 'paused')",
            name="visibility_valid",
        ),
        CheckConstraint(
            "parse_status IN ('empty', 'pending', 'parsed')", name="parse_status_valid"
        ),
        CheckConstraint(
            "parse_source IS NULL OR parse_source IN ('llm', 'template', 'user')",
            name="parse_source_valid",
        ),
        CheckConstraint(
            f"char_length(raw_about_text) <= {ABOUT_TEXT_MAX_LENGTH}", name="about_text_length"
        ),
        CheckConstraint(
            f"char_length(display_name) <= {DISPLAY_NAME_MAX_LENGTH}", name="display_name_length"
        ),
        CheckConstraint(f"cardinality(links) <= {MAX_LINKS}", name="links_count"),
        CheckConstraint(f"cardinality(languages) <= {MAX_LANGUAGES}", name="languages_count"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # Shown to people who receive an intro; never sent to an AI provider.
    display_name: Mapped[str] = mapped_column(
        String(DISPLAY_NAME_MAX_LENGTH), default="", server_default=text("''")
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
    # Optional public links (GitHub, LinkedIn, portfolio): https URLs only, no uploads.
    links: Mapped[list[str]] = mapped_column(
        ARRAY(String(LINK_MAX_LENGTH)), default=list, server_default=text("'{}'::varchar[]")
    )

    # --- parsing (stage 1, ADR 0007) ---------------------------------------------------
    parse_status: Mapped[str] = mapped_column(
        String(16), default=ParseStatus.EMPTY, server_default=text(f"'{ParseStatus.EMPTY}'")
    )
    parse_source: Mapped[str | None] = mapped_column(String(16))
    parse_prompt_version: Mapped[str | None] = mapped_column(String(32))
    # SHA-256 of the about text that ``structured`` was built from: a changed text is
    # re-parsed, an unchanged one never is (hash-based caching).
    parsed_text_hash: Mapped[str | None] = mapped_column(String(64))
    parsed_at: Mapped[datetime | None]

    # --- consent to AI processing of the about text (ADR 0007, section 5) ---------------
    # The wording lives in the client; the API records when and which version was agreed.
    ai_consent_at: Mapped[datetime | None]
    ai_consent_version: Mapped[str | None] = mapped_column(String(32))

    user: Mapped[User] = relationship(back_populates="profile")
