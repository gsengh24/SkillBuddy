"""Profile strength (ADR 0022, screen 10): one checklist, computed here and nowhere else.

The You page meter, Home's "Finish your profile" panel and the returning-visitor popup all
read it from the API. Items are stable codes; clients choose the words and the links.
Also the soft gate (screen 9): sending an intro or joining a team needs a few offered skills.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import Profile

# Offered skills needed before sending an intro or joining a team (screen 9).
MIN_OFFERED_SKILLS: Final = 3
HEADLINE_MIN: Final = 10


class StrengthItem(StrEnum):
    """One checklist item. The order is the order clients list what is missing."""

    INTENTS = "intents"
    OFFERS = "offers"
    WANTS = "wants"
    ABOUT_TEXT = "about_text"
    AVAILABILITY = "availability"
    HEADLINE = "headline"
    LINKS = "links"


@dataclass(frozen=True)
class Strength:
    percent: int
    done: int
    total: int
    missing: list[StrengthItem]


def _checks(profile: Profile) -> dict[StrengthItem, bool]:
    # ``or`` covers a profile not yet flushed, whose server defaults are still None.
    return {
        StrengthItem.INTENTS: bool(profile.intents),
        StrengthItem.OFFERS: len(profile.offer_skills or []) >= MIN_OFFERED_SKILLS,
        StrengthItem.WANTS: bool(profile.want_skills or profile.interest_tags),
        StrengthItem.ABOUT_TEXT: bool((profile.raw_about_text or "").strip()),
        StrengthItem.AVAILABILITY: bool(profile.available_days),
        StrengthItem.HEADLINE: len((profile.headline or "").strip()) >= HEADLINE_MIN,
        StrengthItem.LINKS: bool(profile.links),
    }


def strength_of(profile: Profile | None) -> Strength:
    """The checklist for a profile; no profile yet means nothing is done."""
    total = len(StrengthItem)
    if profile is None:
        return Strength(percent=0, done=0, total=total, missing=list(StrengthItem))
    checks = _checks(profile)
    done = sum(checks.values())
    return Strength(
        percent=round(done * 100 / total),
        done=done,
        total=total,
        missing=[item for item in StrengthItem if not checks[item]],
    )


class SkillsRequiredError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "skills_required"
    default_message = (
        f"Add {MIN_OFFERED_SKILLS} skills you offer first. People decide whether to accept "
        "based on your profile."
    )


async def require_offered_skills(db: AsyncSession, user_id: uuid.UUID) -> None:
    """The soft gate's server rule: raise unless the person offers enough skills."""
    profile = await db.get(Profile, user_id)
    if profile is None or len(profile.offer_skills) < MIN_OFFERED_SKILLS:
        raise SkillsRequiredError
