"""Request and response models for the signed-in user's profile."""

from __future__ import annotations

import uuid
from datetime import datetime, time
from typing import Annotated, Final

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.ai.stages.understand import MAX_ITEMS, Intent, Phrase
from app.models import (
    ABOUT_TEXT_MAX_LENGTH,
    CITY_MAX_LENGTH,
    DISPLAY_NAME_MAX_LENGTH,
    GOAL_MAX_LENGTH,
    HEADLINE_MAX_LENGTH,
    LINK_MAX_LENGTH,
    MAX_LANGUAGES,
    MAX_LINKS,
    ExperienceLevel,
    LocationPrecision,
    ParseSource,
    ParseStatus,
    Profile,
    ProfileVisibility,
    Weekday,
    WeeklyHours,
    WorkingStyle,
)

ABOUT_TEXT_MIN_LENGTH: Final = 20
_REQUEST = ConfigDict(extra="forbid")

DisplayName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=DISPLAY_NAME_MAX_LENGTH),
]
AboutText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=ABOUT_TEXT_MIN_LENGTH, max_length=ABOUT_TEXT_MAX_LENGTH
    ),
]
# https only, with a host: no javascript:, data: or plain-http links.
Link = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        max_length=LINK_MAX_LENGTH,
        pattern=r"^https://[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+(:\d{1,5})?(/[^\s]*)?$",
    ),
]
# IANA name such as "Asia/Kolkata", or "UTC".
Timezone = Annotated[
    str, StringConstraints(max_length=64, pattern=r"^(UTC|[A-Za-z]+(/[A-Za-z0-9_+-]+){1,2})$")
]
# BCP 47 language tag, e.g. "en", "hi", "pa-Guru".
LanguageTag = Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8}){0,2}$")]
Links = Annotated[list[Link], Field(max_length=MAX_LINKS)]
Languages = Annotated[list[LanguageTag], Field(max_length=MAX_LANGUAGES)]
City = Annotated[str, StringConstraints(strip_whitespace=True, max_length=CITY_MAX_LENGTH)]
Headline = Annotated[str, StringConstraints(strip_whitespace=True, max_length=HEADLINE_MAX_LENGTH)]
Goal = Annotated[str, StringConstraints(strip_whitespace=True, max_length=GOAL_MAX_LENGTH)]


def _unique[T](values: list[T]) -> list[T]:
    """Drops repeats, keeping the first of each."""
    return list(dict.fromkeys(values))


Intents = Annotated[list[Intent], Field(max_length=len(Intent)), AfterValidator(_unique)]
Days = Annotated[list[Weekday], Field(max_length=len(Weekday)), AfterValidator(_unique)]


class ProfileIn(BaseModel):
    """Create or replace the profile. A changed about text is parsed in the background."""

    model_config = _REQUEST

    display_name: DisplayName = Field(
        description="Shown to people who receive an intro. Never sent to an AI provider."
    )
    about_text: AboutText = Field(description="The user's own description, in their words.")
    links: Links = Field(default_factory=list)
    timezone: Timezone | None = None
    languages: Languages = Field(default_factory=list)
    visibility: ProfileVisibility = ProfileVisibility.MATCHABLE
    ai_consent: bool = Field(
        default=False,
        description=(
            "The user agrees to the AI-processing consent line shown with the form (ADR 0007, "
            "section 5). Required on the first save and whenever the consent version changes."
        ),
    )


class ProfileSettingsIn(BaseModel):
    """Change settings without touching the about text. Omitted fields stay as they are."""

    model_config = _REQUEST

    display_name: DisplayName | None = None
    links: Links | None = None
    timezone: Timezone | None = None
    languages: Languages | None = None
    visibility: ProfileVisibility | None = Field(
        default=None,
        description=(
            "`matchable`: shown in matches. `after_intro`: people see you only once you "
            "accept their intro (for now treated like `paused`). `paused`: hidden from new "
            "matches; existing chats continue."
        ),
    )
    email_notifications: bool | None = Field(
        default=None, description="Email me when I get an intro or one is accepted."
    )
    city: City | None = Field(default=None, description="An empty string clears it.")
    headline: Headline | None = Field(default=None, description="One line; empty clears it.")
    experience_level: ExperienceLevel | None = Field(default=None, description="`null` clears it.")
    intents: Intents | None = Field(
        default=None, description="What you want from Cynergi in general. Repeats are dropped."
    )
    goal: Goal | None = Field(default=None, description="Your goal right now; empty clears it.")
    working_style: WorkingStyle | None = Field(default=None, description="`null` clears it.")
    weekly_hours: WeeklyHours | None = Field(default=None, description="`null` clears it.")
    available_days: Days | None = None
    available_from: time | None = Field(
        default=None, description="Local time in `timezone`, e.g. `18:00`. `null` clears it."
    )
    available_until: time | None = Field(
        default=None,
        description="May be earlier than `available_from` (past midnight). `null` clears it.",
    )
    location_precision: LocationPrecision | None = Field(
        default=None,
        description=(
            "How much of your city others see: `city`, `country` (shown as nothing until a "
            "country is stored) or `hidden`."
        ),
    )
    show_last_active: bool | None = Field(
        default=None, description="Stored; no one is shown a last-active time yet."
    )
    intros_only_from_strong_matches: bool | None = Field(
        default=None, description="Stored; not enforced yet."
    )
    email_daily_digest: bool | None = Field(
        default=None, description="Unread message digest. Stored; the email is not built yet."
    )
    email_match_suggestions: bool | None = Field(
        default=None, description="Weekly match suggestions. Stored; not built yet."
    )
    email_product_updates: bool | None = Field(
        default=None, description="Occasional product news. Stored; not built yet."
    )


class UnderstandingIn(BaseModel):
    """The user's correction of what was understood from their text."""

    model_config = _REQUEST

    summary: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""
    offers: list[Phrase] = Field(default_factory=list, max_length=MAX_ITEMS)
    seeks: list[Phrase] = Field(default_factory=list, max_length=MAX_ITEMS)
    interests: list[Phrase] = Field(default_factory=list, max_length=MAX_ITEMS)
    availability: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] = ""


class UnderstandingOut(BaseModel):
    summary: str
    offers: list[str]
    seeks: list[str]
    interests: list[str]
    availability: str


class ProfileOut(BaseModel):
    user_id: uuid.UUID
    display_name: str
    about_text: str
    links: list[str]
    timezone: str | None
    languages: list[str]
    visibility: ProfileVisibility
    email_notifications: bool
    city: str
    headline: str
    experience_level: ExperienceLevel | None
    intents: list[Intent]
    goal: str
    working_style: WorkingStyle | None
    weekly_hours: WeeklyHours | None
    available_days: list[Weekday]
    available_from: time | None
    available_until: time | None
    location_precision: LocationPrecision
    show_last_active: bool
    intros_only_from_strong_matches: bool
    email_daily_digest: bool
    email_match_suggestions: bool
    email_product_updates: bool
    parse_status: ParseStatus = Field(
        description="`pending` while the about text is being read; poll until `parsed`."
    )
    parse_source: ParseSource | None
    understanding: UnderstandingOut | None
    ai_consent_version: str | None
    ai_consent_at: datetime | None
    ai_consent_current: bool = Field(
        description="False when the consent version has changed since the user agreed."
    )
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_profile(cls, profile: Profile, *, consent_version: str) -> ProfileOut:
        data = profile.structured or {}
        understanding = None
        if profile.parse_status == ParseStatus.PARSED:
            understanding = UnderstandingOut(
                summary=str(data.get("summary", "")),
                offers=[str(v) for v in data.get("offers", [])],
                seeks=[str(v) for v in data.get("seeks", [])],
                interests=[str(v) for v in data.get("interests", [])],
                availability=str(data.get("availability", "")),
            )
        return cls(
            user_id=profile.user_id,
            display_name=profile.display_name,
            about_text=profile.raw_about_text,
            links=list(profile.links),
            timezone=profile.timezone,
            languages=list(profile.languages),
            visibility=ProfileVisibility(profile.visibility),
            email_notifications=profile.email_notifications,
            city=profile.city,
            headline=profile.headline,
            experience_level=(
                ExperienceLevel(profile.experience_level) if profile.experience_level else None
            ),
            intents=[Intent(value) for value in profile.intents],
            goal=profile.goal,
            working_style=WorkingStyle(profile.working_style) if profile.working_style else None,
            weekly_hours=WeeklyHours(profile.weekly_hours) if profile.weekly_hours else None,
            available_days=[Weekday(value) for value in profile.available_days],
            available_from=profile.available_from,
            available_until=profile.available_until,
            location_precision=LocationPrecision(profile.location_precision),
            show_last_active=profile.show_last_active,
            intros_only_from_strong_matches=profile.intros_only_from_strong_matches,
            email_daily_digest=profile.email_daily_digest,
            email_match_suggestions=profile.email_match_suggestions,
            email_product_updates=profile.email_product_updates,
            parse_status=ParseStatus(profile.parse_status),
            parse_source=ParseSource(profile.parse_source) if profile.parse_source else None,
            understanding=understanding,
            ai_consent_version=profile.ai_consent_version,
            ai_consent_at=profile.ai_consent_at,
            ai_consent_current=profile.ai_consent_version == consent_version,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )
