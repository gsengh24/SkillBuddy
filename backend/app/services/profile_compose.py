"""Step 5 of onboarding (ADR 0022): the about text and the matcher's view from the chips.

``finish`` (in the API request) stores the template text at once and queues
``compose_profile``; this job asks the AI for a better text and replaces the template unless
the person has already edited or confirmed it. The chips are the source of truth for
offers, wants and interests: ``structured`` is built from them, and a later parse of an
edited about text only adds to them (``profile_parsing.with_chips``).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.gateway import AIGateway, Source
from app.ai.stages.compose import PROMPT_ID, Chips, Composed, compose
from app.models import ParseSource, ParseStatus, Profile, Weekday, WeeklyHours
from app.services.profile_parsing import merged_tags, text_hash

logger = logging.getLogger(__name__)

_HOURS: Final = {
    WeeklyHours.ONE_TO_THREE: "1-3 h/week",
    WeeklyHours.FOUR_TO_SIX: "4-6 h/week",
    WeeklyHours.SEVEN_TO_TEN: "7-10 h/week",
    WeeklyHours.TEN_PLUS: "10+ h/week",
}
_WEEKDAYS: Final = {Weekday.MON, Weekday.TUE, Weekday.WED, Weekday.THU, Weekday.FRI}
_WEEKEND: Final = {Weekday.SAT, Weekday.SUN}

AfterCompose = Callable[[AsyncSession, uuid.UUID], Awaitable[None]]


def availability_label(days: Sequence[str], hours: str | None) -> str:
    """ "Weekends · 4-6 h/week", "Mon, Wed", "Weekdays" or ""."""
    picked = {Weekday(day) for day in days}
    if picked == _WEEKEND:
        when = "Weekends"
    elif picked == _WEEKDAYS:
        when = "Weekdays"
    elif picked == _WEEKDAYS | _WEEKEND:
        when = "Any day"
    else:
        when = ", ".join(day.value.title() for day in Weekday if day in picked)
    band = _HOURS.get(WeeklyHours(hours), "") if hours else ""
    return " · ".join(part for part in (when, band) if part)


def chips_of(profile: Profile) -> Chips:
    return Chips(
        intents=list(profile.intents),
        offers=list(profile.offer_skills),
        wants=list(profile.want_skills),
        interests=list(profile.interest_tags),
        note=profile.want_note,
        availability=availability_label(profile.available_days, profile.weekly_hours),
    )


def structured_from_chips(profile: Profile, composed: Composed) -> dict[str, Any]:
    """The ``profiles.structured`` document for a profile made through onboarding."""
    return {
        "summary": composed.summary,
        "title": composed.title,
        "offers": merged_tags(profile.offer_skills, []),
        "seeks": merged_tags(profile.want_skills, []),
        "interests": merged_tags(profile.interest_tags, []),
        "availability": availability_label(profile.available_days, profile.weekly_hours),
    }


async def compose_profile(
    session_factory: async_sessionmaker[AsyncSession],
    gateway: AIGateway,
    user_id: uuid.UUID,
    *,
    after_compose: AfterCompose,
) -> bool:
    """Replace the template about text with the AI's, if nothing changed meanwhile.

    Returns True if the profile was updated. ``after_compose`` runs in the same transaction
    (it queues the embedding) once the person has finished onboarding.
    """
    async with session_factory() as db:
        profile = await db.get(Profile, user_id)
        if profile is None or profile.parse_status != ParseStatus.PENDING:
            return False
        if profile.parse_source != ParseSource.TEMPLATE or not profile.parsed_text_hash:
            return False
        digest = profile.parsed_text_hash
        chips = chips_of(profile)
        names = [profile.display_name] if profile.display_name.strip() else []

    # No transaction is held open during the model call.
    result = await compose(gateway, chips, user_id=str(user_id), name_hints=names)

    async with session_factory() as db:
        profile = await db.scalar(
            select(Profile).where(Profile.user_id == user_id).with_for_update()
        )
        if profile is None or profile.parse_status != ParseStatus.PENDING:
            return False
        if profile.parsed_text_hash != digest:
            return False  # finished again with other chips: that job writes it
        llm = result.source is Source.LLM
        confirmed = profile.onboarding_completed_at is not None
        # The person may already have confirmed the template on step 5: keep their text.
        unchanged = text_hash(profile.raw_about_text) == digest
        if llm and unchanged and not confirmed:
            profile.raw_about_text = result.value.about
            profile.parsed_text_hash = text_hash(result.value.about)
        profile.structured = structured_from_chips(profile, result.value if llm else _kept(profile))
        profile.parse_source = ParseSource.LLM if llm else ParseSource.TEMPLATE
        profile.parse_prompt_version = PROMPT_ID if llm else None
        profile.parsed_at = datetime.now(UTC)
        profile.parse_status = ParseStatus.PARSED
        if confirmed:
            await after_compose(db, user_id)
        await db.commit()
    logger.info(
        "profile_composed",
        extra={
            "source": result.source.value,
            "reason": result.reason.value if result.reason else None,
        },
    )
    return True


def _kept(profile: Profile) -> Composed:
    """The template summary and title already stored (the fallback changes nothing)."""
    data = profile.structured or {}
    return Composed(
        title=str(data.get("title", "")),
        summary=str(data.get("summary", "")),
        about=profile.raw_about_text or "-",
    )
