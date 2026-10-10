"""What a person says about themselves, plus the structure the system derives from it."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, time
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.matching import INTENTS
from app.models.user import GOOGLE_PICTURE_URL_MAX_LENGTH

if TYPE_CHECKING:
    from app.models.user import User

# Text caps (CLAUDE.md, storage rules). Enforced by the API schemas and by CHECKs.
ABOUT_TEXT_MAX_LENGTH = 2000
DISPLAY_NAME_MAX_LENGTH = 60
LINK_MAX_LENGTH = 200
MAX_LINKS = 3
MAX_LANGUAGES = 10
CITY_MAX_LENGTH = 80
HEADLINE_MAX_LENGTH = 80
GOAL_MAX_LENGTH = 300


class ProfileVisibility(StrEnum):
    # Visible to the matcher and to people who receive an intro. There is no public
    # directory: see ARCHITECTURE.md, section 8.
    MATCHABLE = "matchable"
    # "After intro" on the You page: people see you only once you accept their intro.
    # Until the owner settles what that allows, it is treated like PAUSED by matching
    # and intros (the side that shows less).
    AFTER_INTRO = "after_intro"
    # Excluded from new matches; existing connections are unaffected.
    PAUSED = "paused"


class ExperienceLevel(StrEnum):
    JUST_STARTING = "just_starting"
    ONE_TO_THREE_YEARS = "1_3_years"
    THREE_TO_SEVEN_YEARS = "3_7_years"
    SEVEN_PLUS_YEARS = "7_plus_years"


class WorkingStyle(StrEnum):
    ASYNC = "async"
    MIX = "mix"
    LIVE = "live"


class WeeklyHours(StrEnum):
    ONE_TO_THREE = "1_3"
    FOUR_TO_SIX = "4_6"
    SEVEN_TO_TEN = "7_10"
    TEN_PLUS = "10_plus"


class Weekday(StrEnum):
    MON = "mon"
    TUE = "tue"
    WED = "wed"
    THU = "thu"
    FRI = "fri"
    SAT = "sat"
    SUN = "sun"


class LocationPrecision(StrEnum):
    """How much of the city others see."""

    CITY = "city"
    COUNTRY = "country"
    HIDDEN = "hidden"


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _array(values: Sequence[str]) -> str:
    return f"ARRAY[{_in(values)}]::varchar[]"


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
        # The admin Users page's intent filter (intents @> ARRAY[...]).
        Index("ix_profiles_intents", "intents", postgresql_using="gin"),
        CheckConstraint(
            f"visibility IN ({_in(list(ProfileVisibility))})",
            name="visibility_valid",
        ),
        CheckConstraint(f"char_length(city) <= {CITY_MAX_LENGTH}", name="city_length"),
        CheckConstraint(f"char_length(headline) <= {HEADLINE_MAX_LENGTH}", name="headline_length"),
        CheckConstraint(f"char_length(goal) <= {GOAL_MAX_LENGTH}", name="goal_length"),
        CheckConstraint(
            f"experience_level IS NULL OR experience_level IN ({_in(list(ExperienceLevel))})",
            name="experience_level_valid",
        ),
        CheckConstraint(
            f"working_style IS NULL OR working_style IN ({_in(list(WorkingStyle))})",
            name="working_style_valid",
        ),
        CheckConstraint(
            f"weekly_hours IS NULL OR weekly_hours IN ({_in(list(WeeklyHours))})",
            name="weekly_hours_valid",
        ),
        CheckConstraint(f"intents <@ {_array(INTENTS)}", name="intents_valid"),
        CheckConstraint(f"available_days <@ {_array(list(Weekday))}", name="available_days_valid"),
        CheckConstraint(
            f"location_precision IN ({_in(list(LocationPrecision))})",
            name="location_precision_valid",
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

    # --- You page details (all optional; set through PATCH /me/profile) ----------------
    # Free text such as "Bengaluru". Shown to others as ``location_precision`` allows.
    city: Mapped[str] = mapped_column(
        String(CITY_MAX_LENGTH), default="", server_default=text("''")
    )
    headline: Mapped[str] = mapped_column(
        String(HEADLINE_MAX_LENGTH), default="", server_default=text("''")
    )
    experience_level: Mapped[str | None] = mapped_column(String(16))
    # What the person wants from Cynergi in general (a request still picks its own intent).
    intents: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), default=list, server_default=text("'{}'::varchar[]")
    )
    goal: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    working_style: Mapped[str | None] = mapped_column(String(8))
    weekly_hours: Mapped[str | None] = mapped_column(String(8))
    available_days: Mapped[list[str]] = mapped_column(
        ARRAY(String(3)), default=list, server_default=text("'{}'::varchar[]")
    )
    # Local times in ``timezone``; "until" may be earlier than "from" (past midnight).
    available_from: Mapped[time | None]
    available_until: Mapped[time | None]

    # --- privacy -------------------------------------------------------------------------
    location_precision: Mapped[str] = mapped_column(
        String(8),
        default=LocationPrecision.CITY,
        server_default=text(f"'{LocationPrecision.CITY}'"),
    )
    # The picture people the person is connected with see (ADR 0017): a copy of
    # users.google_picture_url while "show my Google photo" is on, otherwise null. Off by
    # default; nobody sees it before a connection.
    photo_url: Mapped[str | None] = mapped_column(String(GOOGLE_PICTURE_URL_MAX_LENGTH))
    # Stored for the You page. Nothing shows anyone's last-active time to others yet.
    show_last_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    # Stored for the You page. Not enforced yet: "strong" needs a score threshold.
    intros_only_from_strong_matches: Mapped[bool] = mapped_column(
        default=False, server_default=text("false")
    )

    # --- email alerts (in-app notifications are always kept) ---------------------------
    # New intro requests, and intros accepted.
    email_notifications: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    # Switches for emails that are not built yet; off until someone turns them on.
    email_daily_digest: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    email_match_suggestions: Mapped[bool] = mapped_column(
        default=False, server_default=text("false")
    )
    email_product_updates: Mapped[bool] = mapped_column(default=False, server_default=text("false"))

    # --- consent to AI processing of the about text (ADR 0007, section 5) ---------------
    # The wording lives in the client; the API records when and which version was agreed.
    ai_consent_at: Mapped[datetime | None]
    ai_consent_version: Mapped[str | None] = mapped_column(String(32))

    user: Mapped[User] = relationship(back_populates="profile")

    def shown_location(self) -> str | None:
        """The location other people see. ``country`` shows nothing until a country is
        stored (only the city is today), so it never reveals more than the person chose."""
        if self.location_precision == LocationPrecision.CITY and self.city:
            return self.city
        return None
