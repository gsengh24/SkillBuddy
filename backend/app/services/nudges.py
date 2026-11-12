"""In-context nudges on Home (ADR 0022, screen 11): one small suggestion after an event.

Rules (owner-approved default, onboarding P4): each kind is shown on one day at most, at
most one kind a day, and a dismissed kind never comes back. "Shown" starts when the API
first hands a nudge out; the same nudge is returned again that day (a reload keeps it) until
it is dismissed or no longer applies. Responses are data only; clients write the words.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Match, MatchRequest, NudgeKind, Profile, Team, TeamMember, User
from app.services.skills import curated_skills

logger = logging.getLogger(__name__)

ORDER: Final = (NudgeKind.TEAM_SKILL, NudgeKind.AVAILABILITY)
ONE_DAY: Final = timedelta(days=1)
# A team joined longer ago than this is no longer "just joined".
RECENT_JOIN: Final = timedelta(days=14)
# Short forms people write in team names, mapped to the listed skill.
ALIASES: Final = {"ml": "Machine learning"}


@dataclass(frozen=True)
class Nudge:
    kind: NudgeKind
    skill: str | None = None
    team_id: uuid.UUID | None = None
    team_name: str | None = None


def _words(text: str) -> str:
    return " " + " ".join(re.findall(r"[a-z0-9+#.]+", text.casefold())) + " "


def skill_named_in(text: str, known: set[str]) -> str | None:
    """The first listed skill named in ``text`` (whole words, any case) not in ``known``."""
    haystack = _words(text)
    for alias, skill in ALIASES.items():
        if f" {alias} " in haystack and skill.casefold() not in known:
            return skill
    for skill in curated_skills():
        if skill.casefold() in known:
            continue
        if _words(skill) in haystack:
            return skill
    return None


class NudgeService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _team_skill(self, profile: Profile, now: datetime) -> Nudge | None:
        rows = await self._db.execute(
            select(Team)
            .join(TeamMember, TeamMember.team_id == Team.id)
            .where(
                TeamMember.user_id == profile.user_id,
                TeamMember.created_at >= now - RECENT_JOIN,
                Team.closed_at.is_(None),
                Team.owner_id.is_distinct_from(profile.user_id),
            )
            .order_by(TeamMember.created_at.desc())
            .limit(5)
        )
        known = {skill.casefold() for skill in profile.offer_skills}
        for team in rows.scalars():
            text = " ".join((team.name, team.description, team.looking_for))
            skill = skill_named_in(text, known)
            if skill is not None:
                return Nudge(
                    NudgeKind.TEAM_SKILL, skill=skill, team_id=team.id, team_name=team.name
                )
        return None

    async def _availability(self, profile: Profile) -> Nudge | None:
        if profile.available_days:
            return None
        matched = await self._db.scalar(
            select(
                exists().where(
                    Match.request_id == MatchRequest.id, MatchRequest.user_id == profile.user_id
                )
            )
        )
        return Nudge(NudgeKind.AVAILABILITY) if matched else None

    async def _build(self, kind: NudgeKind, profile: Profile, now: datetime) -> Nudge | None:
        if kind is NudgeKind.TEAM_SKILL:
            return await self._team_skill(profile, now)
        return await self._availability(profile)

    async def current(self, user: User) -> Nudge | None:
        """Today's nudge, if any; hands out a new one when the day's slot is free."""
        profile = await self._db.scalar(
            select(Profile).where(Profile.user_id == user.id).with_for_update()
        )
        if profile is None or profile.onboarding_completed_at is None:
            return None
        now = datetime.now(UTC)
        if profile.nudge_shown_at is not None and now - profile.nudge_shown_at < ONE_DAY:
            today = NudgeKind(profile.nudges_shown[-1]) if profile.nudges_shown else None
            if today is None or today in profile.nudges_dismissed:
                return None
            return await self._build(today, profile, now)
        for kind in ORDER:
            if kind in profile.nudges_shown:
                continue
            nudge = await self._build(kind, profile, now)
            if nudge is not None:
                profile.nudges_shown = [*profile.nudges_shown, kind.value]
                profile.nudge_shown_at = now
                await self._db.commit()
                logger.info("nudge_shown", extra={"kind": kind.value})
                return nudge
        return None

    async def dismiss(self, user: User, kind: NudgeKind) -> None:
        """Never show this kind again. Idempotent; fine before it was ever shown."""
        profile = await self._db.scalar(
            select(Profile).where(Profile.user_id == user.id).with_for_update()
        )
        if profile is None or kind in profile.nudges_dismissed:
            return
        profile.nudges_dismissed = [*profile.nudges_dismissed, kind.value]
        if kind not in profile.nudges_shown:
            profile.nudges_shown = [*profile.nudges_shown, kind.value]
        await self._db.commit()
        logger.info("nudge_dismissed", extra={"kind": kind.value})
